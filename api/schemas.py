"""API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


# --- Auth ---
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Repos ---
class RepoCreate(BaseModel):
    platform: str
    url: str
    token: str
    autonomy: str = "semi_auto"
    watch_labels: list[str] = ["autoproger"]
    branch_prefix: str = "autoproger/"
    default_branch: str = "main"
    max_file_changes: int = 20
    gitlab_url: str | None = None  # override global GITLAB_URL for this repo


class RepoResponse(BaseModel):
    id: str
    platform: str
    url: str
    autonomy: str
    watch_labels: list
    branch_prefix: str
    default_branch: str
    max_file_changes: int
    gitlab_url: str | None
    created_at: datetime


# --- Tasks ---
class TaskResponse(BaseModel):
    id: str
    repo_id: str
    issue_number: int
    issue_title: str
    issue_body: str
    issue_labels: list
    status: str
    created_at: datetime
    updated_at: datetime


class TaskApproveRequest(BaseModel):
    task_id: str


class TaskCreateRequest(BaseModel):
    repo_id: str
    issue_number: int = 1
    issue_title: str
    issue_body: str = ""
    issue_labels: list[str] = ["autoproger"]


# --- Runs ---
class RunResponse(BaseModel):
    id: str
    task_id: str
    status: str
    agent_results: list[dict[str, Any]]
    pr_url: str | None
    branch_name: str | None
    created_at: datetime
    finished_at: datetime | None


# --- Config ---
class SettingsResponse(BaseModel):
    llm_default_provider: str
    llm_default_model: str
    log_level: str
    # Per-agent turn limits
    claude_code_max_turns_planner: int
    claude_code_max_turns_developer: int
    claude_code_max_turns_reviewer: int
    claude_code_max_turns_tester: int
    # Per-agent budgets (USD, 0 = unlimited)
    claude_code_budget_planner: float
    claude_code_budget_developer: float
    claude_code_budget_reviewer: float
    claude_code_budget_tester: float


class SettingsUpdate(BaseModel):
    llm_default_provider: str | None = None
    llm_default_model: str | None = None
    log_level: str | None = None
    claude_code_max_turns_planner: int | None = None
    claude_code_max_turns_developer: int | None = None
    claude_code_max_turns_reviewer: int | None = None
    claude_code_max_turns_tester: int | None = None
    claude_code_budget_planner: float | None = None
    claude_code_budget_developer: float | None = None
    claude_code_budget_reviewer: float | None = None
    claude_code_budget_tester: float | None = None
