"""GitHub platform client using PyGithub."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Sequence

from github import Github
from github.Repository import Repository as GHRepo

from integrations.base import GitPlatformClient, IssueData, PRData

log = logging.getLogger(__name__)


class GitHubClient(GitPlatformClient):
    def __init__(self, token: str, repo_url: str) -> None:
        self._gh = Github(token)
        self._repo_slug = self._extract_slug(repo_url)
        self._repo: GHRepo | None = None

    @staticmethod
    def _extract_slug(url: str) -> str:
        url = url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        parts = url.replace("https://github.com/", "").replace("http://github.com/", "")
        return parts

    def _get_repo(self) -> GHRepo:
        if self._repo is None:
            self._repo = self._gh.get_repo(self._repo_slug)
        return self._repo

    async def _run(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    async def list_issues(
        self, *, labels: list[str] | None = None, state: str = "open"
    ) -> Sequence[IssueData]:
        repo = self._get_repo()

        def _fetch():
            kw: dict = {"state": state}
            if labels:
                kw["labels"] = [repo.get_label(l) for l in labels]
            return list(repo.get_issues(**kw))

        raw = await self._run(_fetch)
        return [
            IssueData(
                number=i.number,
                title=i.title,
                body=i.body or "",
                labels=[l.name for l in i.labels],
                state=i.state,
                url=i.html_url,
            )
            for i in raw
            if i.pull_request is None  # exclude PRs from issues list
        ]

    async def get_issue(self, number: int) -> IssueData:
        repo = self._get_repo()
        i = await self._run(repo.get_issue, number)
        return IssueData(
            number=i.number,
            title=i.title,
            body=i.body or "",
            labels=[l.name for l in i.labels],
            state=i.state,
            url=i.html_url,
        )

    async def comment_on_issue(self, number: int, body: str) -> None:
        repo = self._get_repo()
        issue = await self._run(repo.get_issue, number)
        await self._run(issue.create_comment, body)

    async def create_pull_request(
        self, *, title: str, body: str, head: str, base: str
    ) -> PRData:
        repo = self._get_repo()

        def _create():
            return repo.create_pull(title=title, body=body, head=head, base=base)

        pr = await self._run(_create)
        return PRData(
            number=pr.number,
            title=pr.title,
            body=pr.body or "",
            url=pr.html_url,
            state=pr.state,
            branch=head,
        )

    async def close_issue(self, number: int) -> None:
        repo = self._get_repo()
        issue = await self._run(repo.get_issue, number)
        await self._run(issue.edit, state="closed")
