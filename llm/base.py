"""Abstract base for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator

from core.models import LLMMessage, LLMResponse, ToolDefinition

if TYPE_CHECKING:
    from llm.claude_code_provider import ClaudeCodeResult


class LLMProvider(ABC):
    """Every LLM backend must implement this interface."""

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse: ...

    @abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @property
    @abstractmethod
    def max_context_tokens(self) -> int: ...

    @property
    @abstractmethod
    def supports_tools(self) -> bool: ...

    @property
    def supports_agentic(self) -> bool:
        """Whether this provider supports agentic execution (file operations, etc.)."""
        return False

    async def execute(
        self,
        prompt: str,
        *,
        cwd: Path | str | None = None,
        system_prompt: str | None = None,
        allowed_tools: list[str] | None = None,
        max_turns: int | None = None,
        timeout: int | None = None,
        session_id: str | None = None,
    ) -> ClaudeCodeResult:
        """Agentic execution — only supported by ClaudeCodeProvider.

        Parameters
        ----------
        session_id : str | None
            Resume a previous Claude Code session (``--resume``).
            Useful for retry loops where the developer agent already
            has context from its first attempt.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support agentic execution. "
            "Use ClaudeCodeProvider for agentic mode."
        )
