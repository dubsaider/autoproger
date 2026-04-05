"""Repository CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from api.schemas import RepoCreate, RepoResponse
from storage.database import async_session
from storage import repositories as db

router = APIRouter(prefix="/api/repos", tags=["repos"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[RepoResponse])
async def list_repos():
    async with async_session() as session:
        repos = await db.list_repos(session)
    return [_repo_response(r) for r in repos]


@router.post("", response_model=RepoResponse, status_code=201)
async def create_repo(body: RepoCreate):
    async with async_session() as session:
        r = await db.create_repo(
            session,
            platform=body.platform,
            url=body.url,
            token=body.token,
            autonomy=body.autonomy,
            watch_labels=body.watch_labels,
            branch_prefix=body.branch_prefix,
            default_branch=body.default_branch,
            max_file_changes=body.max_file_changes,
            gitlab_url=body.gitlab_url,
        )
    return _repo_response(r)


def _repo_response(r) -> RepoResponse:
    return RepoResponse(
        id=r.id,
        platform=r.platform,
        url=r.url,
        autonomy=r.autonomy,
        watch_labels=r.watch_labels,
        branch_prefix=r.branch_prefix,
        default_branch=r.default_branch,
        max_file_changes=r.max_file_changes,
        gitlab_url=r.gitlab_url,
        created_at=r.created_at,
    )


@router.delete("/{repo_id}", status_code=204)
async def delete_repo(repo_id: str):
    async with async_session() as session:
        ok = await db.delete_repo(session, repo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Repo not found")
