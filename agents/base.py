"""Common interfaces for all specialized agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AgentResult:
    """Normalized output from any agent execution."""

    success: bool
    summary: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class BaseAgent:
    """Shared protocol for role agents."""

    role_name: str = "base"

    def run(self, payload: dict[str, Any]) -> AgentResult:
        raise NotImplementedError("Agent must implement run()")
