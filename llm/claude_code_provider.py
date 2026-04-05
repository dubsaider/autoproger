"""Claude Code CLI provider — primary LLM backend.

Uses the headless Agent SDK mode (`claude --bare -p`) for non-interactive,
scripted execution.  Prompts are piped via stdin to avoid OS argv length limits.

Two output modes:
  - json   (`--output-format json`)        — single JSON blob after completion
  - stream (`--output-format stream-json`)  — newline-delimited JSON events

Key CLI flags used:
  --bare                skip hooks / MCP / auto-memory for fast, predictable startup
  -p                    headless (print) mode — no interactive UI
  --allowedTools        auto-approve listed tools so `-p` never hangs on a prompt
  --append-system-prompt  add role instructions while keeping Claude Code defaults
  --resume SESSION_ID   continue a previous conversation (useful for retry loops)
  --max-turns / --max-budget-usd  safety limits
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

from core.models import LLMMessage, LLMResponse, ToolDefinition
from llm.base import LLMProvider

log = logging.getLogger(__name__)

# ── Tool sets for different agent roles ──────────────────────────────────

TOOLS_DEVELOPER = [
    "Read", "Write", "Edit", "MultiEdit",
    "Glob", "Grep", "LS",
    "Bash",
]

TOOLS_READONLY = [
    "Read", "Glob", "Grep", "LS",
    "Bash",
]

TOOLS_TEST = [
    "Read", "Write", "Edit", "MultiEdit",
    "Glob", "Grep", "LS",
    "Bash",
]


# ── Result dataclass ────────────────────────────────────────────────────

@dataclass
class ClaudeCodeResult:
    """Parsed result from a single `claude -p` invocation."""

    content: str = ""
    is_error: bool = False
    session_id: str = ""
    cost_usd: float = 0.0
    duration_ms: int = 0
    num_turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    raw_json: dict = field(default_factory=dict)


# ── Stream event (one line of stream-json output) ──────────────────────

@dataclass
class StreamEvent:
    """Single event from `--output-format stream-json`."""

    type: str = ""
    subtype: str = ""
    content: str = ""
    tool: str = ""
    session_id: str = ""
    raw: dict = field(default_factory=dict)


# ── Provider ────────────────────────────────────────────────────────────

class ClaudeCodeProvider(LLMProvider):
    """Primary LLM provider — wraps `claude --bare -p`.

    Works with a Claude Pro/Max subscription or an Anthropic API key
    configured in Claude Code's own settings.
    """

    def __init__(
        self,
        binary: str = "claude",
        default_max_turns: int = 15,
        timeout: int = 600,
        max_budget_usd: float | None = None,
        model: str | None = None,
    ) -> None:
        self._binary = binary
        self._default_max_turns = default_max_turns
        self._timeout = timeout
        self._max_budget_usd = max_budget_usd
        self._model = model

        if not shutil.which(binary):
            raise FileNotFoundError(
                f"'{binary}' not found on PATH. "
                "Install: https://docs.anthropic.com/en/docs/claude-code"
            )

    # ── LLMProvider properties ──────────────────────────────────────────

    @property
    def model_name(self) -> str:
        return self._model or "claude-code"

    @property
    def max_context_tokens(self) -> int:
        return 200_000

    @property
    def supports_tools(self) -> bool:
        return True

    @property
    def supports_agentic(self) -> bool:
        return True

    # ── Standard completion interface ───────────────────────────────────

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        prompt = self._messages_to_prompt(messages)
        system = self._extract_system(messages)
        result = await self._invoke(prompt, system_prompt=system)
        return LLMResponse(
            content=result.content,
            tokens_input=result.input_tokens,
            tokens_output=result.output_tokens,
            model=self.model_name,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        resp = await self.complete(messages, temperature=temperature, max_tokens=max_tokens)
        yield resp.content

    # ── Agentic execution (the core capability) ────────────────────────

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
        max_budget_usd: float | None = None,
    ) -> ClaudeCodeResult:
        """Run Claude Code in agentic mode on a directory.

        Claude reads/writes files, runs commands, and iteratively solves
        problems in *cwd*.  The prompt is piped via stdin.
        """
        return await self._invoke(
            prompt,
            cwd=cwd,
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            max_turns=max_turns,
            timeout=timeout,
            session_id=session_id,
            max_budget_usd=max_budget_usd,
        )

    async def execute_streaming(
        self,
        prompt: str,
        *,
        cwd: Path | str | None = None,
        system_prompt: str | None = None,
        allowed_tools: list[str] | None = None,
        max_turns: int | None = None,
        timeout: int | None = None,
        session_id: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Run Claude Code and yield events in real time (stream-json)."""
        args = self._build_args(
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            max_turns=max_turns,
            session_id=session_id,
            output_format="stream-json",
            verbose=True,
        )

        log.info(
            "Claude Code stream: cwd=%s tools=%s max_turns=%s",
            cwd or ".", allowed_tools or "all", max_turns or self._default_max_turns,
        )

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
        )

        assert proc.stdin is not None
        proc.stdin.write(prompt.encode("utf-8"))
        proc.stdin.close()

        assert proc.stdout is not None
        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            yield StreamEvent(
                type=data.get("type", ""),
                subtype=data.get("subtype", ""),
                content=data.get("content", {}).get("text", "") if isinstance(data.get("content"), dict) else str(data.get("content", "")),
                tool=data.get("tool", ""),
                session_id=data.get("session_id", ""),
                raw=data,
            )

        await proc.wait()

    # ── Convenience methods ─────────────────────────────────────────────

    async def execute_developer(
        self,
        prompt: str,
        cwd: Path | str,
        *,
        system_prompt: str | None = None,
        max_turns: int = 15,
        session_id: str | None = None,
    ) -> ClaudeCodeResult:
        """Full read / write / edit / bash access."""
        return await self.execute(
            prompt, cwd=cwd, system_prompt=system_prompt,
            allowed_tools=TOOLS_DEVELOPER, max_turns=max_turns,
            session_id=session_id,
        )

    async def execute_readonly(
        self,
        prompt: str,
        cwd: Path | str,
        *,
        system_prompt: str | None = None,
        max_turns: int = 5,
        session_id: str | None = None,
    ) -> ClaudeCodeResult:
        """Read-only access — inspect files and run safe commands."""
        return await self.execute(
            prompt, cwd=cwd, system_prompt=system_prompt,
            allowed_tools=TOOLS_READONLY, max_turns=max_turns,
            session_id=session_id,
        )

    async def execute_tester(
        self,
        prompt: str,
        cwd: Path | str,
        *,
        system_prompt: str | None = None,
        max_turns: int = 15,
        session_id: str | None = None,
    ) -> ClaudeCodeResult:
        """Write tests and run them."""
        return await self.execute(
            prompt, cwd=cwd, system_prompt=system_prompt,
            allowed_tools=TOOLS_TEST, max_turns=max_turns,
            session_id=session_id,
        )

    # ── Internal ────────────────────────────────────────────────────────

    def _build_args(
        self,
        *,
        system_prompt: str | None = None,
        allowed_tools: list[str] | None = None,
        max_turns: int | None = None,
        session_id: str | None = None,
        output_format: str = "json",
        verbose: bool = False,
        max_budget_usd: float | None = None,
    ) -> list[str]:
        args = [self._binary, "-p", "--output-format", output_format]

        if verbose:
            args.append("--verbose")

        if self._model:
            args.extend(["--model", self._model])

        if system_prompt:
            args.extend(["--append-system-prompt", system_prompt])

        if allowed_tools:
            args.extend(["--allowedTools", ",".join(allowed_tools)])

        turns = max_turns or self._default_max_turns
        args.extend(["--max-turns", str(turns)])

        # per-call budget overrides the provider-level default
        effective_budget = max_budget_usd if max_budget_usd is not None else self._max_budget_usd
        if effective_budget:
            args.extend(["--max-budget-usd", str(effective_budget)])

        if session_id:
            args.extend(["--resume", session_id])

        return args

    async def _invoke(
        self,
        prompt: str,
        *,
        cwd: Path | str | None = None,
        system_prompt: str | None = None,
        allowed_tools: list[str] | None = None,
        max_turns: int | None = None,
        timeout: int | None = None,
        session_id: str | None = None,
        max_budget_usd: float | None = None,
    ) -> ClaudeCodeResult:
        args = self._build_args(
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            max_turns=max_turns,
            session_id=session_id,
            max_budget_usd=max_budget_usd,
        )

        log.info(
            "Claude Code invoke: cwd=%s tools=%s max_turns=%s session=%s",
            cwd or ".",
            allowed_tools or "all",
            max_turns or self._default_max_turns,
            session_id or "new",
        )
        log.debug("Claude Code args: %s", " ".join(args))

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
        )

        effective_timeout = timeout or self._timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode("utf-8")),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            log.error("Claude Code timed out after %ds", effective_timeout)
            return ClaudeCodeResult(
                content="",
                is_error=True,
                duration_ms=effective_timeout * 1000,
            )

        raw = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()

        if err:
            if proc.returncode and proc.returncode != 0:
                log.warning("Claude Code stderr: %s", err[:2000])
            else:
                log.debug("Claude Code stderr: %s", err[:1000])

        if proc.returncode and proc.returncode != 0:
            log.warning("Claude Code exited with code %d | stdout_len=%d", proc.returncode, len(raw))

        return self._parse_result(raw, proc.returncode or 0)

    def _parse_result(self, raw: str, returncode: int) -> ClaudeCodeResult:
        if not raw:
            return ClaudeCodeResult(content="", is_error=True)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return ClaudeCodeResult(
                content=raw,
                is_error=(returncode != 0),
            )

        usage = data.get("usage", {})
        subtype = data.get("subtype", "")
        is_error = data.get("is_error", returncode != 0)

        # Include subtype in content so callers can inspect the stop reason
        content = data.get("result", data.get("content", ""))
        if is_error and not content and subtype:
            content = subtype  # e.g. "error_max_turns", "error_during_execution"

        if is_error:
            log.warning("Claude Code is_error=True subtype=%s turns=%s cost=$%s",
                        subtype, data.get("num_turns"), data.get("total_cost_usd"))

        return ClaudeCodeResult(
            content=content,
            is_error=is_error,
            session_id=data.get("session_id", ""),
            cost_usd=data.get("total_cost_usd", data.get("cost_usd", 0.0)),
            duration_ms=data.get("duration_ms", 0),
            num_turns=data.get("num_turns", 0),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            raw_json=data,
        )

    @staticmethod
    def _extract_system(messages: list[LLMMessage]) -> str | None:
        for m in messages:
            if m.role == "system":
                return m.content
        return None

    @staticmethod
    def _messages_to_prompt(messages: list[LLMMessage]) -> str:
        parts = []
        for m in messages:
            if m.role == "system":
                continue
            elif m.role == "user":
                parts.append(m.content)
            elif m.role == "assistant":
                parts.append(f"[Previous response]\n{m.content}")
        return "\n\n".join(parts)
