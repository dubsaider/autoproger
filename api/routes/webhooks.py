"""Incoming webhook endpoints for GitHub/GitLab events."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from core.models import Platform, RepoConfig
from core.task_manager import TaskManager
from integrations.base import IssueData
from storage.database import async_session
from storage import repositories as db

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
log = logging.getLogger(__name__)
task_manager = TaskManager()


@router.post("/github")
async def github_webhook(request: Request):
    """Handle GitHub webhook events (issues opened)."""
    event = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()

    if event == "issues" and payload.get("action") == "opened":
        issue = payload["issue"]
        repo_url = payload["repository"]["html_url"]

        async with async_session() as session:
            repos = await db.list_repos(session)
            cfg = next(
                (r for r in repos if r.url.rstrip("/") == repo_url.rstrip("/")),
                None,
            )

        if cfg is None:
            log.warning("Webhook for unknown repo: %s", repo_url)
            return {"status": "ignored", "reason": "repo not configured"}

        labels = [l["name"] for l in issue.get("labels", [])]
        watch = cfg.watch_labels or ["autoproger"]
        if not any(lbl in watch for lbl in labels):
            return {"status": "ignored", "reason": "no matching label"}

        repo_cfg = RepoConfig(
            id=cfg.id,
            platform=Platform.GITHUB,
            url=cfg.url,
            token=cfg.token,
            autonomy=cfg.autonomy,
            watch_labels=cfg.watch_labels,
            branch_prefix=cfg.branch_prefix,
            default_branch=cfg.default_branch,
            max_file_changes=cfg.max_file_changes,
        )
        issue_data = IssueData(
            number=issue["number"],
            title=issue["title"],
            body=issue.get("body", ""),
            labels=labels,
            state=issue["state"],
            url=issue["html_url"],
        )
        await task_manager.create_task_from_issue(repo_cfg, issue_data)
        return {"status": "task_created"}

    return {"status": "ignored", "event": event}


@router.post("/gitlab")
async def gitlab_webhook(request: Request):
    """Handle GitLab webhook events (issue opened)."""
    payload = await request.json()
    kind = payload.get("object_kind", "")

    if kind == "issue":
        attrs = payload.get("object_attributes", {})
        if attrs.get("action") != "open":
            return {"status": "ignored", "reason": "not an open event"}

        project = payload.get("project", {})
        repo_url = project.get("web_url", "")

        async with async_session() as session:
            repos = await db.list_repos(session)
            cfg = next(
                (r for r in repos if r.url.rstrip("/") == repo_url.rstrip("/")),
                None,
            )

        if cfg is None:
            return {"status": "ignored", "reason": "repo not configured"}

        labels = [l["title"] for l in payload.get("labels", [])]
        watch = cfg.watch_labels or ["autoproger"]
        if not any(lbl in watch for lbl in labels):
            return {"status": "ignored", "reason": "no matching label"}

        repo_cfg = RepoConfig(
            id=cfg.id,
            platform=Platform.GITLAB,
            url=cfg.url,
            token=cfg.token,
            autonomy=cfg.autonomy,
            watch_labels=cfg.watch_labels,
            branch_prefix=cfg.branch_prefix,
            default_branch=cfg.default_branch,
            max_file_changes=cfg.max_file_changes,
        )
        issue_data = IssueData(
            number=attrs["iid"],
            title=attrs["title"],
            body=attrs.get("description", ""),
            labels=labels,
            state=attrs["state"],
            url=attrs["url"],
        )
        await task_manager.create_task_from_issue(repo_cfg, issue_data)
        return {"status": "task_created"}

    return {"status": "ignored", "kind": kind}
