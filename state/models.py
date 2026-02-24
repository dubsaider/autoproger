"""Core state models for orchestrated multi-agent runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class TaskStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    NEEDS_INPUT = "needs_input"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class RunRequest:
    source: str  # manual | github_event
    text: str
    repo_path: str
    repo_slug: str = ""
    issue_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Task:
    id: str
    title: str
    owner: str
    acceptance_criteria: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.QUEUED
    attempts: int = 0
    last_error: str = ""


@dataclass(slots=True)
class AgentExecution:
    id: str
    run_id: str
    agent: str
    task_id: str
    status: str
    started_at: str
    finished_at: str = ""
    summary: str = ""
    warnings: list[str] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class QualityGate:
    id: str
    run_id: str
    name: str
    status: str = "pending"  # pending | pass | fail | skip
    details: str = ""
    updated_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class Run:
    id: str
    source: str
    input_text: str
    repo_path: str
    repo_slug: str
    branch_name: str
    status: RunStatus = RunStatus.PENDING
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    tasks: list[Task] = field(default_factory=list)
    executions: list[AgentExecution] = field(default_factory=list)
    quality_gates: list[QualityGate] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)
    retry_limit: int = 3
    last_error: str = ""

    @classmethod
    def create(cls, request: RunRequest, branch_name: str, retry_limit: int = 3) -> "Run":
        return cls(
            id=str(uuid4()),
            source=request.source,
            input_text=request.text.strip(),
            repo_path=request.repo_path,
            repo_slug=request.repo_slug,
            branch_name=branch_name,
            status=RunStatus.PENDING,
            retry_limit=retry_limit,
        )

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        for task in data["tasks"]:
            if isinstance(task.get("status"), TaskStatus):
                task["status"] = task["status"].value
        return data


def run_from_dict(payload: dict[str, Any]) -> Run:
    tasks = [
        Task(
            id=t["id"],
            title=t["title"],
            owner=t["owner"],
            acceptance_criteria=t.get("acceptance_criteria", []),
            dependencies=t.get("dependencies", []),
            status=TaskStatus(t.get("status", TaskStatus.QUEUED.value)),
            attempts=t.get("attempts", 0),
            last_error=t.get("last_error", ""),
        )
        for t in payload.get("tasks", [])
    ]
    executions = [
        AgentExecution(
            id=e["id"],
            run_id=e["run_id"],
            agent=e["agent"],
            task_id=e["task_id"],
            status=e["status"],
            started_at=e["started_at"],
            finished_at=e.get("finished_at", ""),
            summary=e.get("summary", ""),
            warnings=e.get("warnings", []),
            artifacts=e.get("artifacts", {}),
        )
        for e in payload.get("executions", [])
    ]
    gates = [
        QualityGate(
            id=g["id"],
            run_id=g["run_id"],
            name=g["name"],
            status=g.get("status", "pending"),
            details=g.get("details", ""),
            updated_at=g.get("updated_at", utc_now()),
        )
        for g in payload.get("quality_gates", [])
    ]
    return Run(
        id=payload["id"],
        source=payload["source"],
        input_text=payload["input_text"],
        repo_path=payload["repo_path"],
        repo_slug=payload.get("repo_slug", ""),
        branch_name=payload["branch_name"],
        status=RunStatus(payload.get("status", RunStatus.PENDING.value)),
        created_at=payload.get("created_at", utc_now()),
        updated_at=payload.get("updated_at", utc_now()),
        tasks=tasks,
        executions=executions,
        quality_gates=gates,
        outputs=payload.get("outputs", {}),
        retry_limit=payload.get("retry_limit", 3),
        last_error=payload.get("last_error", ""),
    )
