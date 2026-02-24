"""Quality gate execution with pass/fail transition rules."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class GateResult:
    name: str
    status: str  # pass | fail | skip
    output: str = ""


@dataclass(slots=True)
class QualityGateRunner:
    lint_cmd: list[str] = field(default_factory=lambda: ["python", "-m", "compileall", "."])
    test_cmd: list[str] = field(default_factory=lambda: ["pytest", "-q"])
    build_cmd: list[str] = field(default_factory=lambda: ["python", "-m", "compileall", "."])
    smoke_cmd: list[str] = field(default_factory=lambda: ["python", "-c", "print('smoke-ok')"])

    def run_all(self, repo_path: Path) -> list[GateResult]:
        return [
            self._run_gate("lint", self.lint_cmd, repo_path),
            self._run_gate("unit_integration", self.test_cmd, repo_path),
            self._run_gate("build", self.build_cmd, repo_path),
            self._run_gate("smoke", self.smoke_cmd, repo_path),
        ]

    def failed_gates(self, results: list[GateResult]) -> list[str]:
        return [gate.name for gate in results if gate.status == "fail"]

    @staticmethod
    def _run_gate(name: str, cmd: list[str], repo_path: Path) -> GateResult:
        try:
            proc = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except FileNotFoundError:
            return GateResult(name=name, status="skip", output=f"Command not found: {cmd[0]}")
        except subprocess.TimeoutExpired:
            return GateResult(name=name, status="fail", output="Timed out")

        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        if proc.returncode == 0:
            return GateResult(name=name, status="pass", output=output.strip())
        return GateResult(name=name, status="fail", output=output.strip())
