"""GitLab platform client using python-gitlab."""

from __future__ import annotations

import asyncio
import logging
import re
from functools import partial
from typing import Sequence

import gitlab

from integrations.base import GitPlatformClient, IssueData, PRData

log = logging.getLogger(__name__)


class GitLabClient(GitPlatformClient):
    def __init__(self, token: str, repo_url: str, gitlab_url: str = "https://gitlab.com") -> None:
        self._gl = gitlab.Gitlab(gitlab_url, private_token=token)
        self._project_path = self._extract_path(repo_url, gitlab_url)
        self._project = None

    @staticmethod
    def _extract_path(repo_url: str, gitlab_url: str) -> str:
        url = repo_url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        url = re.sub(r"https?://[^/]+/", "", url)
        return url

    def _get_project(self):
        if self._project is None:
            self._project = self._gl.projects.get(self._project_path)
        return self._project

    async def _run(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    async def list_issues(
        self, *, labels: list[str] | None = None, state: str = "open"
    ) -> Sequence[IssueData]:
        project = self._get_project()
        gl_state = "opened" if state == "open" else state

        def _fetch():
            kw: dict = {"state": gl_state}
            if labels:
                kw["labels"] = labels
            return list(project.issues.list(**kw, get_all=True))

        raw = await self._run(_fetch)
        return [
            IssueData(
                number=i.iid,
                title=i.title,
                body=i.description or "",
                labels=i.labels,
                state=i.state,
                url=i.web_url,
            )
            for i in raw
        ]

    async def get_issue(self, number: int) -> IssueData:
        project = self._get_project()
        i = await self._run(project.issues.get, number)
        return IssueData(
            number=i.iid,
            title=i.title,
            body=i.description or "",
            labels=i.labels,
            state=i.state,
            url=i.web_url,
        )

    async def comment_on_issue(self, number: int, body: str) -> None:
        project = self._get_project()
        issue = await self._run(project.issues.get, number)
        await self._run(issue.notes.create, {"body": body})

    async def create_pull_request(
        self, *, title: str, body: str, head: str, base: str
    ) -> PRData:
        project = self._get_project()

        def _create():
            return project.mergerequests.create({
                "source_branch": head,
                "target_branch": base,
                "title": title,
                "description": body,
            })

        mr = await self._run(_create)
        return PRData(
            number=mr.iid,
            title=mr.title,
            body=mr.description or "",
            url=mr.web_url,
            state=mr.state,
            branch=head,
        )

    async def close_issue(self, number: int) -> None:
        project = self._get_project()
        issue = await self._run(project.issues.get, number)
        await self._run(issue.save, state_event="close")
