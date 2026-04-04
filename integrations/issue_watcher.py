"""Polls git platforms for new issues with target labels."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

from core.models import Platform, RepoConfig
from integrations.base import GitPlatformClient, IssueData
from integrations.github_client import GitHubClient
from integrations.gitlab_client import GitLabClient

log = logging.getLogger(__name__)

OnNewIssue = Callable[[RepoConfig, IssueData], Awaitable[None]]


def _build_client(cfg: RepoConfig) -> GitPlatformClient:
    if cfg.platform == Platform.GITHUB:
        return GitHubClient(token=cfg.token, repo_url=cfg.url)
    elif cfg.platform == Platform.GITLAB:
        from core.config import get_settings
        return GitLabClient(
            token=cfg.token, repo_url=cfg.url, gitlab_url=get_settings().gitlab_url
        )
    raise ValueError(f"Unsupported platform: {cfg.platform}")


class IssueWatcher:
    """Periodically polls repositories for new issues matching configured labels."""

    def __init__(
        self,
        repos: list[RepoConfig],
        on_new_issue: OnNewIssue,
        poll_interval: int = 60,
    ) -> None:
        self._repos = repos
        self._on_new_issue = on_new_issue
        self._poll_interval = poll_interval
        self._seen: dict[str, set[int]] = {}  # repo_id -> set of issue numbers
        self._running = False

    async def start(self) -> None:
        self._running = True
        log.info("IssueWatcher started, polling every %ds for %d repos",
                 self._poll_interval, len(self._repos))
        while self._running:
            for cfg in self._repos:
                try:
                    await self._poll_repo(cfg)
                except Exception:
                    log.exception("Error polling repo %s", cfg.url)
            await asyncio.sleep(self._poll_interval)

    def stop(self) -> None:
        self._running = False

    async def _poll_repo(self, cfg: RepoConfig) -> None:
        client = _build_client(cfg)
        issues = await client.list_issues(labels=cfg.watch_labels, state="open")

        seen = self._seen.setdefault(cfg.id, set())
        for issue in issues:
            if issue.number not in seen:
                seen.add(issue.number)
                log.info("New issue #%d in %s: %s", issue.number, cfg.url, issue.title)
                await self._on_new_issue(cfg, issue)

    def update_repos(self, repos: list[RepoConfig]) -> None:
        self._repos = repos
        current_ids = {r.id for r in repos}
        for rid in list(self._seen):
            if rid not in current_ids:
                del self._seen[rid]
