"""Модели данных для пайплайна."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class IssueStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"


@dataclass
class Issue:
    """Issue из репозитория."""
    number: int
    title: str
    body: str
    labels: list[str]
    state: str
    html_url: str
    raw: Any = None

    @property
    def ref(self) -> str:
        return f"#{self.number}"


@dataclass
class WorkPlan:
    """План работ по задаче."""
    issue_ref: str
    summary: str
    steps: list[str]
    files_to_touch: list[str] = field(default_factory=list)
    branch_name: str = ""


@dataclass
class PipelineContext:
    """Контекст выполнения пайплайна по одному issue."""
    issue: Issue
    plan: WorkPlan | None = None
    branch_name: str = ""
    mr_url: str = ""
    skipped_reason: str | None = None  # если задано — issue пропущен (например, неактуален)
    started_at: datetime = field(default_factory=datetime.utcnow)
    logs: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.logs.append(f"[{datetime.utcnow().isoformat()}] {message}")
