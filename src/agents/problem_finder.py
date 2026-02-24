"""Агент поиска проблем в репозитории (эвристики + LLM)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from src.llm import ask


def _detect_test_command(repo_path: Path) -> list[str] | None:
    """Определяет тестовую команду без зависимости от legacy-модулей."""
    if (repo_path / "package.json").exists():
        data = (repo_path / "package.json").read_text(encoding="utf-8", errors="ignore")
        if "scripts" in data and '"test"' in data:
            return ["npm", "test"]
        return ["npm", "run", "test"]
    if (repo_path / "pytest.ini").exists() or (repo_path / "pyproject.toml").exists():
        return ["pytest"]
    if (repo_path / "tox.ini").exists():
        return ["tox"]
    if (repo_path / "Makefile").exists():
        return ["make", "test"]
    return None


def _safe_read(path: Path, max_chars: int = 6000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return text[:max_chars]
    except Exception:
        return ""


def _collect_todo_markers(repo_path: Path, limit: int = 40) -> list[dict]:
    markers = ("TODO", "FIXME", "HACK", "XXX")
    findings: list[dict] = []
    skip_dirs = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
    count = 0
    for p in repo_path.rglob("*"):
        if count >= limit:
            break
        if not p.is_file():
            continue
        if any(part in skip_dirs for part in p.parts):
            continue
        if p.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".rb", ".php", ".md"}:
            continue
        text = _safe_read(p, max_chars=20000)
        if not text:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if any(m in line for m in markers):
                findings.append(
                    {
                        "severity": "medium",
                        "title": "Есть технический долг/незавершённая задача",
                        "file": str(p.relative_to(repo_path)),
                        "description": f"Найден маркер: {line.strip()[:220]}",
                        "hint": "Проверить, нужно ли закрыть TODO/FIXME или создать issue на доработку.",
                    }
                )
                count += 1
                if count >= limit:
                    break
    return findings


def _quick_test_failure(repo_path: Path) -> list[dict]:
    cmd = _detect_test_command(repo_path)
    if not cmd:
        return []
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode == 0:
            return []
        out = (result.stdout or "") + "\n" + (result.stderr or "")
        return [
            {
                "severity": "high",
                "title": "Тесты падают",
                "file": "",
                "description": out.strip()[:600],
                "hint": f"Запустить {' '.join(cmd)} локально и исправить падения.",
            }
        ]
    except Exception:
        return []


def _collect_context_files(repo_path: Path) -> list[tuple[str, str]]:
    patterns = [
        "README.md",
        "pyproject.toml",
        "package.json",
        "Dockerfile",
        "docker-compose.yml",
        "requirements.txt",
        "src",
        "app",
    ]
    files: list[tuple[str, str]] = []
    skip_dirs = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
    for p in repo_path.rglob("*"):
        if len(files) >= 8:
            break
        if not p.is_file():
            continue
        if any(part in skip_dirs for part in p.parts):
            continue
        rel = str(p.relative_to(repo_path))
        if not any(token in rel for token in patterns):
            continue
        text = _safe_read(p, max_chars=2200)
        if not text:
            continue
        files.append((rel, text))
    return files


def _parse_llm_findings(text: str) -> list[dict]:
    """
    Ожидаемый формат:
    - severity|title|file|description|hint
    """
    findings: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or not line.startswith("-"):
            continue
        line = line[1:].strip()
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 5:
            continue
        severity, title, file, description, hint = parts[:5]
        sev = severity.lower()
        if sev not in {"low", "medium", "high", "critical"}:
            sev = "medium"
        findings.append(
            {
                "severity": sev,
                "title": title or "Потенциальная проблема",
                "file": file,
                "description": description,
                "hint": hint,
            }
        )
    return findings


def scan_repo_problems(
    repo_path: Path,
    repo_name: str,
    *,
    llm_provider: str = "cursor",
    anthropic_api_key: str = "",
    claude_model: str = "claude-sonnet-4-20250514",
    cursor_cli_cmd: str = "cursor agent",
    cursor_timeout_sec: int = 120,
    run_tests: bool = False,
) -> list[dict]:
    """
    Ищет проблемы в репозитории:
    1) эвристики (TODO/FIXME), 2) опционально падения тестов, 3) LLM-анализ контекста.
    """
    findings = _collect_todo_markers(repo_path)
    if run_tests:
        findings.extend(_quick_test_failure(repo_path))

    context_files = _collect_context_files(repo_path)
    context_block = "\n\n".join(
        f"FILE: {rel}\n{text}" for rel, text in context_files
    )[:18000]
    prompt = f"""Найди потенциальные проблемы в репозитории {repo_name}.

Контекст файлов:
{context_block}

Верни до 8 находок в формате (по одной строке):
- severity|title|file|description|hint

severity: low/medium/high/critical
Пиши коротко и по делу.
"""
    llm_text = ask(
        prompt,
        provider=llm_provider if llm_provider in ("claude", "cursor", "none") else "none",
        cursor_cli_cmd=cursor_cli_cmd,
        cursor_cwd=repo_path,
        cursor_timeout_sec=cursor_timeout_sec,
        anthropic_api_key=anthropic_api_key,
        claude_model=claude_model,
    )
    if llm_text:
        findings.extend(_parse_llm_findings(llm_text))

    # Убираем явные дубли (по title+file+description)
    uniq = []
    seen = set()
    for f in findings:
        key = (f.get("title", ""), f.get("file", ""), f.get("description", ""))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)
    return uniq[:30]

