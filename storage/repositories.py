"""CRUD helpers over ORM models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import RepoORM, RunORM, TaskORM


# ---------------------------------------------------------------------------
# Repos
# ---------------------------------------------------------------------------

async def create_repo(session: AsyncSession, **kwargs) -> RepoORM:
    repo = RepoORM(**kwargs)
    session.add(repo)
    await session.commit()
    await session.refresh(repo)
    return repo


async def get_repo(session: AsyncSession, repo_id: str) -> RepoORM | None:
    return await session.get(RepoORM, repo_id)


async def list_repos(session: AsyncSession) -> Sequence[RepoORM]:
    result = await session.execute(select(RepoORM).order_by(RepoORM.created_at.desc()))
    return result.scalars().all()


async def delete_repo(session: AsyncSession, repo_id: str) -> bool:
    repo = await session.get(RepoORM, repo_id)
    if repo is None:
        return False
    await session.delete(repo)
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

async def create_task(session: AsyncSession, **kwargs) -> TaskORM:
    task = TaskORM(**kwargs)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_task(session: AsyncSession, task_id: str) -> TaskORM | None:
    return await session.get(TaskORM, task_id)


async def list_tasks(
    session: AsyncSession,
    *,
    repo_id: str | None = None,
    status: str | None = None,
) -> Sequence[TaskORM]:
    q = select(TaskORM).order_by(TaskORM.created_at.desc())
    if repo_id:
        q = q.where(TaskORM.repo_id == repo_id)
    if status:
        q = q.where(TaskORM.status == status)
    result = await session.execute(q)
    return result.scalars().all()


async def update_task_status(session: AsyncSession, task_id: str, status: str) -> None:
    await session.execute(
        update(TaskORM)
        .where(TaskORM.id == task_id)
        .values(status=status, updated_at=datetime.now(timezone.utc))
    )
    await session.commit()


async def save_checkpoint(session: AsyncSession, task_id: str, checkpoint: dict) -> None:
    await session.execute(
        update(TaskORM)
        .where(TaskORM.id == task_id)
        .values(checkpoint=checkpoint, updated_at=datetime.now(timezone.utc))
    )
    await session.commit()


async def get_checkpoint(session: AsyncSession, task_id: str) -> dict:
    task = await session.get(TaskORM, task_id)
    return task.checkpoint if task and task.checkpoint else {}


async def clear_checkpoint(session: AsyncSession, task_id: str) -> None:
    await session.execute(
        update(TaskORM)
        .where(TaskORM.id == task_id)
        .values(checkpoint={}, updated_at=datetime.now(timezone.utc))
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

async def create_run(session: AsyncSession, **kwargs) -> RunORM:
    run = RunORM(**kwargs)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def get_run(session: AsyncSession, run_id: str) -> RunORM | None:
    return await session.get(RunORM, run_id)


async def list_runs(session: AsyncSession, task_id: str | None = None) -> Sequence[RunORM]:
    q = select(RunORM).order_by(RunORM.created_at.desc())
    if task_id:
        q = q.where(RunORM.task_id == task_id)
    result = await session.execute(q)
    return result.scalars().all()


async def update_run_results(
    session: AsyncSession,
    run_id: str,
    *,
    agent_results: list,
) -> None:
    await session.execute(
        update(RunORM).where(RunORM.id == run_id).values(agent_results=agent_results)
    )
    await session.commit()


async def finish_run(
    session: AsyncSession,
    run_id: str,
    *,
    status: str,
    agent_results: list | None = None,
    pr_url: str | None = None,
    branch_name: str | None = None,
) -> None:
    values: dict = {
        "status": status,
        "finished_at": datetime.now(timezone.utc),
    }
    if agent_results is not None:
        values["agent_results"] = agent_results
    if pr_url is not None:
        values["pr_url"] = pr_url
    if branch_name is not None:
        values["branch_name"] = branch_name
    await session.execute(update(RunORM).where(RunORM.id == run_id).values(**values))
    await session.commit()
