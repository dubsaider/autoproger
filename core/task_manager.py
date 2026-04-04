"""Task Manager: creates and manages tasks from incoming issues."""

from __future__ import annotations

import logging

from core.models import Autonomy, RepoConfig, Task, TaskStatus
from integrations.base import IssueData
from storage.database import async_session
from storage import repositories as repo_db

log = logging.getLogger(__name__)


class TaskManager:
    async def create_task_from_issue(
        self, cfg: RepoConfig, issue: IssueData
    ) -> Task:
        task = Task(
            repo_id=cfg.id,
            issue_number=issue.number,
            issue_title=issue.title,
            issue_body=issue.body,
            issue_labels=issue.labels,
            status=(
                TaskStatus.APPROVED
                if cfg.autonomy == Autonomy.FULL_AUTO
                else TaskStatus.PENDING
            ),
        )
        async with async_session() as session:
            await repo_db.create_task(
                session,
                id=task.id,
                repo_id=task.repo_id,
                issue_number=task.issue_number,
                issue_title=task.issue_title,
                issue_body=task.issue_body,
                issue_labels=task.issue_labels,
                status=task.status,
            )
        log.info(
            "Task %s created from issue #%d (%s) [status=%s]",
            task.id, issue.number, issue.title, task.status,
        )
        return task

    async def approve_task(self, task_id: str) -> None:
        async with async_session() as session:
            await repo_db.update_task_status(session, task_id, TaskStatus.APPROVED)
        log.info("Task %s approved", task_id)

    async def update_status(self, task_id: str, status: TaskStatus) -> None:
        async with async_session() as session:
            await repo_db.update_task_status(session, task_id, status)

    async def get_pending_tasks(self, repo_id: str | None = None) -> list:
        async with async_session() as session:
            return list(
                await repo_db.list_tasks(session, repo_id=repo_id, status=TaskStatus.PENDING)
            )

    async def get_approved_tasks(self, repo_id: str | None = None) -> list:
        async with async_session() as session:
            return list(
                await repo_db.list_tasks(session, repo_id=repo_id, status=TaskStatus.APPROVED)
            )
