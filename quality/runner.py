"""Quality gates runner: lint, test, build checks on the local repo."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class GateResult:
    name: str
    passed: bool
    output: str = ""
    error: str = ""


@dataclass
class QualityReport:
    gates: list[GateResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(g.passed for g in self.gates)

    @property
    def summary(self) -> str:
        lines = []
        for g in self.gates:
            status = "PASS" if g.passed else "FAIL"
            lines.append(f"[{status}] {g.name}")
            if g.error:
                lines.append(f"  Error: {g.error}")
        return "\n".join(lines)


async def _run_command(cmd: str, cwd: Path, timeout: int = 120) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout.decode(errors="replace")
    except asyncio.TimeoutError:
        return 1, f"Command timed out after {timeout}s"
    except Exception as exc:
        return 1, str(exc)


async def run_quality_gates(repo_path: Path) -> QualityReport:
    report = QualityReport()

    # Detect which checks are applicable
    checks: list[tuple[str, str]] = []

    if (repo_path / "pyproject.toml").exists() or (repo_path / "setup.py").exists():
        if (repo_path / "ruff.toml").exists() or _pyproject_has(repo_path, "ruff"):
            checks.append(("ruff lint", "ruff check ."))
        checks.append(("pytest", "python -m pytest --tb=short -q"))

    if (repo_path / "package.json").exists():
        checks.append(("npm lint", "npm run lint --if-present"))
        checks.append(("npm test", "npm test --if-present"))

    if not checks:
        report.gates.append(GateResult(name="no-checks", passed=True, output="No checks detected"))
        return report

    for name, cmd in checks:
        code, output = await _run_command(cmd, repo_path)
        report.gates.append(GateResult(
            name=name,
            passed=(code == 0),
            output=output[:2000],
            error="" if code == 0 else f"Exit code {code}",
        ))

    log.info("Quality gates: %s", "ALL PASS" if report.all_passed else "SOME FAILED")
    return report


def _pyproject_has(repo_path: Path, section: str) -> bool:
    pp = repo_path / "pyproject.toml"
    if pp.exists():
        try:
            return section in pp.read_text(encoding="utf-8")
        except Exception:
            pass
    return False
