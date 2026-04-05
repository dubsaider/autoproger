"""Run history endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from core.progress import get_events
from api.schemas import RunResponse
from storage.database import async_session
from storage import repositories as db

router = APIRouter(prefix="/api/runs", tags=["runs"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[RunResponse])
async def list_runs(task_id: str | None = None):
    async with async_session() as session:
        runs = await db.list_runs(session, task_id=task_id)
    return [
        RunResponse(
            id=r.id,
            task_id=r.task_id,
            status=r.status,
            agent_results=r.agent_results or [],
            pr_url=r.pr_url,
            branch_name=r.branch_name,
            created_at=r.created_at,
            finished_at=r.finished_at,
        )
        for r in runs
    ]


@router.get("/{run_id}/progress")
async def run_progress(run_id: str):
    """Return live progress events for an in-flight run."""
    return get_events(run_id)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: str):
    async with async_session() as session:
        r = await db.get_run(session, run_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunResponse(
        id=r.id,
        task_id=r.task_id,
        status=r.status,
        agent_results=r.agent_results or [],
        pr_url=r.pr_url,
        branch_name=r.branch_name,
        created_at=r.created_at,
        finished_at=r.finished_at,
    )
