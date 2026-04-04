"""Routes LLM calls to the configured provider.

Claude Code CLI is the primary provider and is registered first.
API-based providers (Anthropic, OpenRouter) are registered as fallbacks.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from core.config import get_settings
from core.models import LLMMessage, LLMResponse, ToolDefinition
from llm.base import LLMProvider

log = logging.getLogger(__name__)


class LLMRouter:
    """Holds registered providers and routes requests."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._default: str | None = None

    def register(self, name: str, provider: LLMProvider, *, default: bool = False) -> None:
        self._providers[name] = provider
        if default or self._default is None:
            self._default = name

    def get(self, name: str | None = None) -> LLMProvider:
        key = name or self._default
        if key is None or key not in self._providers:
            available = list(self._providers.keys())
            raise RuntimeError(
                f"LLM provider '{key}' not registered. Available: {available}"
            )
        return self._providers[key]

    @property
    def default_name(self) -> str | None:
        return self._default

    @property
    def available(self) -> list[str]:
        return list(self._providers.keys())

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        provider: str | None = None,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        p = self.get(provider)
        log.debug("LLM complete via %s (%s)", provider or self._default, p.model_name)
        return await p.complete(
            messages, tools=tools, temperature=temperature, max_tokens=max_tokens
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        provider: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        p = self.get(provider)
        async for chunk in p.stream(
            messages, temperature=temperature, max_tokens=max_tokens
        ):
            yield chunk


def build_router() -> LLMRouter:
    """Create an LLMRouter with all available providers.

    Priority: Claude Code CLI > Anthropic API > OpenRouter.
    """
    settings = get_settings()
    router = LLMRouter()

    # 1. Claude Code CLI — primary provider, no API key required
    try:
        from llm.claude_code_provider import ClaudeCodeProvider

        router.register(
            "claude_code",
            ClaudeCodeProvider(
                binary=settings.claude_code_binary,
                default_max_turns=settings.claude_code_max_turns,
                timeout=settings.claude_code_timeout,
                max_budget_usd=settings.claude_code_max_budget_usd or None,
                model=settings.claude_code_model or None,
            ),
            default=(settings.llm_default_provider == "claude_code"),
        )
        log.info("Claude Code CLI registered as LLM provider")
    except FileNotFoundError:
        log.warning(
            "Claude Code CLI ('%s') not found on PATH — "
            "install it or configure an API-based provider",
            settings.claude_code_binary,
        )
    except Exception:
        log.exception("Failed to initialize Claude Code CLI")

    # 2. Anthropic API — fallback, requires API key
    if settings.anthropic_api_key:
        from llm.anthropic_provider import AnthropicProvider

        router.register(
            "anthropic",
            AnthropicProvider(
                api_key=settings.anthropic_api_key,
                model=settings.llm_default_model,
            ),
            default=(settings.llm_default_provider == "anthropic"),
        )
        log.info("Anthropic API registered as LLM provider")

    # 3. OpenRouter — another fallback
    if settings.openrouter_api_key:
        from llm.openrouter_provider import OpenRouterProvider

        router.register(
            "openrouter",
            OpenRouterProvider(api_key=settings.openrouter_api_key),
            default=(settings.llm_default_provider == "openrouter"),
        )
        log.info("OpenRouter registered as LLM provider")

    if not router.available:
        log.error(
            "No LLM providers available! Install Claude Code CLI "
            "or set ANTHROPIC_API_KEY / OPENROUTER_API_KEY"
        )

    return router
