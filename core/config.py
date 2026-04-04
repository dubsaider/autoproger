from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM — Claude Code CLI is the primary provider
    llm_default_provider: Literal["claude_code", "anthropic", "openrouter"] = "claude_code"
    llm_default_model: str = "claude-sonnet-4-20250514"
    claude_code_binary: str = "claude"
    claude_code_max_turns: int = 15
    claude_code_timeout: int = 600
    claude_code_max_budget_usd: float = 0
    claude_code_model: str = ""

    # API keys (optional — only needed for API-based providers)
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/autoproger.db"

    # Auth
    secret_key: str = "change-me-to-random-secret"
    admin_username: str = "admin"
    admin_password: str = "admin"
    access_token_expire_minutes: int = 1440

    # Telegram
    telegram_bot_token: str = ""
    telegram_admin_chat_id: str = ""

    # Git platforms
    github_token: str = ""
    gitlab_token: str = ""
    gitlab_url: str = "https://gitlab.com"

    # General
    workdir: Path = Path("./data/repos")
    log_level: str = "INFO"

    @property
    def workdir_abs(self) -> Path:
        p = self.workdir if self.workdir.is_absolute() else Path.cwd() / self.workdir
        p.mkdir(parents=True, exist_ok=True)
        return p


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
