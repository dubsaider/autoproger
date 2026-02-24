"""Конфигурация системы."""
import os
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Репозиторий
    repo_provider: Literal["github", "gitlab"] = Field(default="github", alias="REPO_PROVIDER")
    repo_owner: str = Field(default="", alias="GITHUB_OWNER")
    repo_name: str = Field(default="", alias="GITHUB_REPO")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    gitlab_token: str = Field(default="", alias="GITLAB_TOKEN")
    gitlab_project_id: str = Field(default="", alias="GITLAB_PROJECT_ID")

    # Локальный путь к клону репо (для реализации и тестов)
    repo_path: Path = Field(default=Path("."), alias="REPO_PATH")

    # Автор коммитов (если задан — коммиты будут от этого аккаунта, например бота)
    # Для GitHub лучше указать no-reply email: username@users.noreply.github.com
    git_author_name: str = Field(default="", alias="GIT_AUTHOR_NAME")
    git_author_email: str = Field(default="", alias="GIT_AUTHOR_EMAIL")

    # LLM для анализа и планов: claude (API) | cursor (локальный Cursor CLI) | none
    llm_provider: Literal["claude", "cursor", "none"] = Field(default="cursor", alias="LLM_PROVIDER")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    claude_model: str = Field(default="claude-sonnet-4-20250514", alias="CLAUDE_MODEL")
    # Команда для Cursor CLI (запуск в каталоге репо). Пример: cursor agent или "cursor agent"
    cursor_cli_cmd: str = Field(default="cursor agent", alias="CURSOR_CLI_CMD")
    cursor_timeout_sec: int = Field(default=120, alias="CURSOR_TIMEOUT_SEC")

    # Поведение
    issue_labels_filter: list[str] = Field(default_factory=list, alias="ISSUE_LABELS")  # пусто = все
    auto_assign_issues: bool = Field(default=False, alias="AUTO_ASSIGN_ISSUES")
    create_draft_mr: bool = Field(default=True, alias="CREATE_DRAFT_MR")
    # Проверка актуальности: по меткам всегда; при True — дополнительно запрос к LLM
    actuality_check_llm: bool = Field(default=False, alias="ACTUALITY_CHECK_LLM")


def get_settings() -> Settings:
    return Settings()
