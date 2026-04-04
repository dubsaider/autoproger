"""Task management endpoints."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api.auth import get_current_user
from api.schemas import TaskApproveRequest, TaskCreateRequest, TaskResponse
from core.models import Autonomy, Platform, RepoConfig, Task, TaskStatus
from core.orchestrator import Orchestrator
from core.task_manager import TaskManager
from integrations.base import IssueData
from integrations.github_client import GitHubClient
from integrations.gitlab_client import GitLabClient
from llm.router import build_router
from storage.database import async_session
from storage import repositories as db

router = APIRouter(prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(get_current_user)])
task_manager = TaskManager()
log = logging.getLogger(__name__)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(repo_id: str | None = None, status: str | None = None):
    async with async_session() as session:
        tasks = await db.list_tasks(session, repo_id=repo_id, status=status)
    return [_task_response(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    async with async_session() as session:
        t = await db.get_task(session, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_response(t)


@router.post("/approve")
async def approve_task(body: TaskApproveRequest):
    await task_manager.approve_task(body.task_id)
    return {"status": "approved", "task_id": body.task_id}


@router.post("/create", response_model=TaskResponse, status_code=201)
async def create_task(body: TaskCreateRequest):
    """Manually create a task (simulate an incoming issue)."""
    async with async_session() as session:
        repo = await db.get_repo(session, body.repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")

    repo_cfg = _repo_orm_to_cfg(repo)
    issue = IssueData(
        number=body.issue_number,
        title=body.issue_title,
        body=body.issue_body,
        labels=body.issue_labels,
        state="open",
        url="",
    )
    task = await task_manager.create_task_from_issue(repo_cfg, issue)
    async with async_session() as session:
        t = await db.get_task(session, task.id)
    return _task_response(t)


@router.post("/{task_id}/run")
async def run_task(task_id: str, background_tasks: BackgroundTasks):
    """Trigger the orchestrator pipeline for a task.

    The pipeline runs in the background; poll GET /api/tasks/{id}
    and GET /api/runs?task_id={id} for progress.
    """
    async with async_session() as session:
        task_orm = await db.get_task(session, task_id)
    if task_orm is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_orm.status not in (TaskStatus.APPROVED, TaskStatus.PENDING):
        raise HTTPException(
            status_code=400,
            detail=f"Task status is '{task_orm.status}', expected 'approved' or 'pending'",
        )

    async with async_session() as session:
        repo_orm = await db.get_repo(session, task_orm.repo_id)
    if repo_orm is None:
        raise HTTPException(status_code=404, detail="Repo not found for this task")

    if task_orm.status == TaskStatus.PENDING:
        await task_manager.approve_task(task_id)

    background_tasks.add_task(_run_pipeline, task_orm, repo_orm)
    return {
        "status": "started",
        "task_id": task_id,
        "message": "Pipeline started in background. Poll /api/tasks/{id} and /api/runs for progress.",
    }


async def _run_pipeline(task_orm, repo_orm):
    """Execute the orchestrator pipeline in the background."""
    try:
        llm_router = build_router()
    except Exception:
        log.exception("Failed to build LLM router")
        async with async_session() as session:
            await db.update_task_status(session, task_orm.id, TaskStatus.FAILED)
        return

    repo_cfg = _repo_orm_to_cfg(repo_orm)

    platform_client = _build_platform_client(repo_cfg)

    task = Task(
        id=task_orm.id,
        repo_id=task_orm.repo_id,
        issue_number=task_orm.issue_number,
        issue_title=task_orm.issue_title,
        issue_body=task_orm.issue_body,
        issue_labels=task_orm.issue_labels,
        status=TaskStatus.APPROVED,
    )

    orchestrator = Orchestrator(llm_router)

    try:
        log.info("Pipeline started for task %s", task.id)
        run = await orchestrator.execute(task, repo_cfg, platform_client)
        log.info("Pipeline finished for task %s: status=%s pr=%s", task.id, run.status, run.pr_url)
    except Exception:
        log.exception("Pipeline failed for task %s", task.id)


def _repo_orm_to_cfg(repo_orm) -> RepoConfig:
    return RepoConfig(
        id=repo_orm.id,
        platform=Platform(repo_orm.platform),
        url=repo_orm.url,
        token=repo_orm.token,
        autonomy=Autonomy(repo_orm.autonomy),
        watch_labels=repo_orm.watch_labels or ["autoproger"],
        branch_prefix=repo_orm.branch_prefix,
        default_branch=repo_orm.default_branch,
        max_file_changes=repo_orm.max_file_changes,
    )


def _build_platform_client(cfg: RepoConfig):
    if cfg.platform == Platform.GITHUB:
        return GitHubClient(token=cfg.token, repo_url=cfg.url)
    elif cfg.platform == Platform.GITLAB:
        from core.config import get_settings
        return GitLabClient(
            token=cfg.token,
            repo_url=cfg.url,
            gitlab_url=get_settings().gitlab_url,
        )
    raise ValueError(f"Unknown platform: {cfg.platform}")


def _task_response(t) -> TaskResponse:
    return TaskResponse(
        id=t.id,
        repo_id=t.repo_id,
        issue_number=t.issue_number,
        issue_title=t.issue_title,
        issue_body=t.issue_body,
        issue_labels=t.issue_labels,
        status=t.status,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )
