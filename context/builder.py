"""Builds context for an agent: selects relevant files and composes a prompt section."""

from __future__ import annotations

import logging
from pathlib import Path

from context.indexer import RepoIndex

log = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 120_000  # ~30k tokens budget for context


def _keyword_relevance(file_path: str, keywords: list[str]) -> int:
    score = 0
    lower = file_path.lower()
    for kw in keywords:
        if kw.lower() in lower:
            score += 2
    return score


def select_relevant_files(
    repo_path: Path,
    index: RepoIndex,
    *,
    keywords: list[str],
    max_chars: int = DEFAULT_MAX_CHARS,
    languages: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Return list of (relative_path, content) pairs most relevant to the task."""
    candidates: list[tuple[int, str]] = []
    for fi in index.files:
        if languages and fi.language not in languages:
            continue
        score = _keyword_relevance(fi.path, keywords)
        # Boost smaller files (more likely to be focused)
        if fi.lines < 200:
            score += 1
        candidates.append((score, fi.path))

    candidates.sort(key=lambda x: (-x[0], x[1]))

    result: list[tuple[str, str]] = []
    total = 0
    for _score, rel in candidates:
        fp = repo_path / rel
        try:
            content = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if total + len(content) > max_chars:
            if result:
                break
            content = content[:max_chars]
        result.append((rel, content))
        total += len(content)

    return result


def build_context_prompt(
    repo_path: Path,
    index: RepoIndex,
    *,
    issue_title: str,
    issue_body: str,
    extra_keywords: list[str] | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    """Compose a context block to prepend to agent prompts."""
    keywords = (issue_title + " " + issue_body).split()[:20]
    if extra_keywords:
        keywords.extend(extra_keywords)

    files = select_relevant_files(repo_path, index, keywords=keywords, max_chars=max_chars)

    parts = [
        f"## Repository structure ({index.total_files} files, {index.total_lines} lines)\n",
        "Languages: " + ", ".join(f"{k}({v})" for k, v in sorted(
            index.languages.items(), key=lambda x: -x[1]
        )[:8]),
        "",
    ]

    for rel, content in files:
        parts.append(f"### {rel}")
        parts.append(f"```\n{content}\n```")
        parts.append("")

    return "\n".join(parts)
