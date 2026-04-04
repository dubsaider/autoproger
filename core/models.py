"""Domain models shared across the system (Pydantic)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TaskStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRole(StrEnum):
    PLANNER = "planner"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    TESTER = "tester"


class Autonomy(StrEnum):
    FULL_AUTO = "full_auto"
    SEMI_AUTO = "semi_auto"
    MANUAL = "manual"


class Platform(StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"


# ---------------------------------------------------------------------------
# Repo configuration
# ---------------------------------------------------------------------------

class RepoConfig(BaseModel):
    id: str = Field(default_factory=_new_id)
    platform: Platform
    url: str
    token: str
    autonomy: Autonomy = Autonomy.SEMI_AUTO
    watch_labels: list[str] = Field(default_factory=lambda: ["autoproger"])
    branch_prefix: str = "autoproger/"
    llm_provider: str | None = None
    max_file_changes: int = 20
    allowed_paths: list[str] = Field(default_factory=lambda: ["**"])
    denied_paths: list[str] = Field(default_factory=list)
    default_branch: str = "main"


# ---------------------------------------------------------------------------
# Task / Run
# ---------------------------------------------------------------------------

class Task(BaseModel):
    id: str = Field(default_factory=_new_id)
    repo_id: str
    issue_number: int
    issue_title: str
    issue_body: str = ""
    issue_labels: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class AgentResult(BaseModel):
    role: AgentRole
    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    tokens_used: int = 0
    duration_ms: int = 0


class Run(BaseModel):
    id: str = Field(default_factory=_new_id)
    task_id: str
    status: TaskStatus = TaskStatus.IN_PROGRESS
    agent_results: list[AgentResult] = Field(default_factory=list)
    pr_url: str | None = None
    branch_name: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None


# ---------------------------------------------------------------------------
# LLM layer shared types
# ---------------------------------------------------------------------------

class LLMMessage(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    content: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tokens_input: int = 0
    tokens_output: int = 0
    model: str = ""


# ---------------------------------------------------------------------------
# File change produced by Developer agent
# ---------------------------------------------------------------------------

class FileChange(BaseModel):
    path: str
    action: str  # "create" | "modify" | "delete"
    content: str | None = None
    diff: str | None = None
