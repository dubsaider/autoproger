"""Indexes a local repository to build a structural map."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "target", "vendor",
}

LANG_MAP: dict[str, str] = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".jsx": "javascript", ".go": "go",
    ".rs": "rust", ".java": "java", ".rb": "ruby", ".php": "php",
    ".c": "c", ".cpp": "cpp", ".h": "c", ".cs": "csharp",
    ".swift": "swift", ".kt": "kotlin", ".scala": "scala",
    ".md": "markdown", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".html": "html", ".css": "css", ".scss": "scss",
    ".sql": "sql", ".sh": "shell", ".dockerfile": "docker",
}

MAX_FILE_SIZE = 512 * 1024  # skip files > 512 KB


@dataclass
class FileInfo:
    path: str
    language: str
    size: int
    lines: int


@dataclass
class RepoIndex:
    root: str
    files: list[FileInfo] = field(default_factory=list)
    languages: dict[str, int] = field(default_factory=dict)
    total_files: int = 0
    total_lines: int = 0

    @property
    def tree_summary(self) -> str:
        lines: list[str] = []
        for f in sorted(self.files, key=lambda x: x.path):
            lines.append(f"  {f.path}  ({f.language}, {f.lines}L)")
        return "\n".join(lines)


def index_repo(repo_path: Path) -> RepoIndex:
    idx = RepoIndex(root=str(repo_path))
    for item in sorted(repo_path.rglob("*")):
        if any(part in IGNORE_DIRS for part in item.parts):
            continue
        if not item.is_file():
            continue
        if item.stat().st_size > MAX_FILE_SIZE:
            continue

        rel = str(item.relative_to(repo_path)).replace("\\", "/")
        lang = LANG_MAP.get(item.suffix.lower(), "other")

        try:
            content = item.read_text(encoding="utf-8", errors="ignore")
            line_count = content.count("\n") + 1
        except Exception:
            line_count = 0

        fi = FileInfo(path=rel, language=lang, size=item.stat().st_size, lines=line_count)
        idx.files.append(fi)
        idx.languages[lang] = idx.languages.get(lang, 0) + 1
        idx.total_files += 1
        idx.total_lines += line_count

    log.info("Indexed %s: %d files, %d lines", repo_path.name, idx.total_files, idx.total_lines)
    return idx
