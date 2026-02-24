"""Security and safety helpers for orchestration runtime."""

from __future__ import annotations

import hashlib
from typing import Any


SENSITIVE_KEYS = {"token", "password", "secret", "apikey", "api_key"}


def mask_secret(value: str) -> str:
    if not value:
        return ""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"***{digest}"


def sanitize_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = key.lower()
        if any(sensitive in lowered for sensitive in SENSITIVE_KEYS):
            cleaned[key] = mask_secret(str(value))
        elif isinstance(value, dict):
            cleaned[key] = sanitize_mapping(value)
        else:
            cleaned[key] = value
    return cleaned
