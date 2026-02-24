"""Pydantic-схемы для API админки."""
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Конфиг, сохраняемый из UI
class RepoItem(BaseModel):
    id: str | int
    name: str
    path_with_namespace: str | None = None
    web_url: str = ""


class ConnectionConfig(BaseModel):
    provider: Literal["github", "gitlab"] = "gitlab"
    # GitLab
    gitlab_url: str = Field(default="https://gitlab.com", description="URL GitLab сервера")
    gitlab_token: str = ""
    selected_projects: list[RepoItem] = Field(default_factory=list)
    # GitHub
    github_token: str = ""
    selected_repos: list[RepoItem] = Field(default_factory=list)
    # Общее
    repo_path_base: str = Field(default="", description="Базовый каталог для клонов репозиториев")
    git_author_name: str = ""
    git_author_email: str = ""
    create_draft_mr: bool = True
    issue_labels: list[str] = Field(default_factory=list)
    llm_provider: str = "cursor"  # "claude" | "cursor" | "none"
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    cursor_cli_cmd: str = "cursor agent"
    cursor_timeout_sec: int = 120
    actuality_check_llm: bool = False


class ConfigResponse(BaseModel):
    config: ConnectionConfig


class GitLabProjectsRequest(BaseModel):
    gitlab_url: str
    token: str
    search: str = ""


class GitHubReposRequest(BaseModel):
    token: str
    search: str = ""


class IssueDraftRequest(BaseModel):
    brief: str
    repo: str | None = None


class IssueDraftResponse(BaseModel):
    title: str
    body: str
    labels: list[str] = Field(default_factory=list)
    repo: str


class IssueCreateRequest(BaseModel):
    title: str
    body: str
    labels: list[str] = Field(default_factory=list)
    repo: str | None = None


class IssueCreateResponse(BaseModel):
    number: int
    title: str
    html_url: str
    repo: str


class ProblemScanRequest(BaseModel):
    repo: str | None = None
    run_tests: bool = False


class ProblemItem(BaseModel):
    severity: str
    title: str
    file: str = ""
    description: str
    hint: str = ""


class ProblemScanResponse(BaseModel):
    repo: str
    findings: list[ProblemItem] = Field(default_factory=list)


class RepoCloneRequest(BaseModel):
    repo: str | None = None
    clone_all: bool = False
    pull_if_exists: bool = True


class RepoCloneItem(BaseModel):
    repo: str
    local_path: str
    status: str  # cloned | pulled | exists | error
    message: str = ""


class RepoCloneResponse(BaseModel):
    results: list[RepoCloneItem] = Field(default_factory=list)
