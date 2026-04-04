"""Token-aware text chunking utilities."""

from __future__ import annotations

CHARS_PER_TOKEN = 4  # rough estimate for English/code


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    max_chars = max_tokens * CHARS_PER_TOKEN
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


def chunk_text(text: str, max_tokens: int, overlap_tokens: int = 200) -> list[str]:
    """Split text into chunks of at most max_tokens with overlap."""
    max_chars = max_tokens * CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap_chars
        if start <= (end - max_chars):
            break
    return chunks
