"""Base agent class. All specialised agents inherit from this."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path

from core.models import AgentResult, AgentRole, LLMMessage
from llm.base import LLMProvider

log = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base for all agents.

    Supports two execution paths:
    - Completion mode: build messages -> LLM complete -> parse response
    - Agentic mode:    build prompt  -> Claude Code execute in repo dir -> parse result

    In agentic mode the *session_id* returned by Claude Code is stored
    on the AgentResult (``output["session_id"]``) so callers can pass it
    back for retry/follow-up calls via ``--resume``.
    """

    role: AgentRole

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    @abstractmethod
    def _build_messages(self, **kwargs) -> list[LLMMessage]:
        """Build message chain for completion mode."""
        ...

    def _build_agentic_prompt(self, **kwargs) -> str:
        """Build a single prompt for agentic execution. Override in subclasses."""
        msgs = self._build_messages(**kwargs)
        parts = [m.content for m in msgs if m.role == "user"]
        return "\n\n".join(parts)

    def _system_prompt(self, **kwargs) -> str | None:
        """Extract system prompt for agentic execution."""
        msgs = self._build_messages(**kwargs)
        for m in msgs:
            if m.role == "system":
                return m.content
        return None

    async def run(self, **kwargs) -> AgentResult:
        """Execute the agent.

        Uses agentic mode if the provider supports it and *cwd* is given.
        Pass ``session_id`` in kwargs to resume a previous Claude Code session.
        """
        t0 = time.monotonic()
        try:
            cwd = kwargs.get("cwd")
            if self._llm.supports_agentic and cwd:
                return await self._run_agentic(t0, **kwargs)
            return await self._run_completion(t0, **kwargs)
        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            log.exception("%s agent failed", self.role)
            return AgentResult(
                role=self.role,
                success=False,
                error=str(exc),
                duration_ms=elapsed,
            )

    # ── Completion path ─────────────────────────────────────────────────

    async def _run_completion(self, t0: float, **kwargs) -> AgentResult:
        messages = self._build_messages(**kwargs)
        resp = await self._llm.complete(messages, max_tokens=8192)
        elapsed = int((time.monotonic() - t0) * 1000)
        output = self._parse_response(resp.content)
        return AgentResult(
            role=self.role,
            success=True,
            output=output,
            tokens_used=resp.tokens_input + resp.tokens_output,
            duration_ms=elapsed,
        )

    # ── Agentic path ───────────────────────────────────────────────────

    async def _run_agentic(self, t0: float, **kwargs) -> AgentResult:
        prompt = self._build_agentic_prompt(**kwargs)
        system = self._system_prompt(**kwargs)
        cwd = kwargs["cwd"]
        allowed_tools = self._agentic_tools()
        max_turns = self._agentic_max_turns()
        session_id = kwargs.get("session_id")

        result = await self._llm.execute(
            prompt,
            cwd=cwd,
            system_prompt=system,
            allowed_tools=allowed_tools,
            max_turns=max_turns,
            session_id=session_id,
        )

        elapsed = int((time.monotonic() - t0) * 1000)
        if result.is_error:
            return AgentResult(
                role=self.role,
                success=False,
                error=result.content or "Claude Code execution failed",
                tokens_used=result.input_tokens + result.output_tokens,
                duration_ms=result.duration_ms or elapsed,
            )

        output = self._parse_agentic_result(result)
        output["session_id"] = result.session_id
        return AgentResult(
            role=self.role,
            success=True,
            output=output,
            tokens_used=result.input_tokens + result.output_tokens,
            duration_ms=result.duration_ms or elapsed,
        )

    # ── Override points ─────────────────────────────────────────────────

    def _agentic_tools(self) -> list[str] | None:
        """Override to restrict tools in agentic mode."""
        return None

    def _agentic_max_turns(self) -> int:
        return 10

    def _parse_response(self, content: str) -> dict:
        """Parse LLM completion response. Override for structured parsing."""
        return {"raw": content}

    def _parse_agentic_result(self, result) -> dict:
        """Parse Claude Code agentic result. Override for structured parsing."""
        return {
            "raw": result.content,
            "num_turns": result.num_turns,
            "cost_usd": result.cost_usd,
        }
