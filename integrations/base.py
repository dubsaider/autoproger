"""Abstract base for git platform clients (GitHub, GitLab)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence


@dataclass
class IssueData:
    number: int
    title: str
    body: str
    labels: list[str]
    state: str
    url: str


@dataclass
class PRData:
    number: int
    title: str
    body: str
    url: str
    state: str
    branch: str


class GitPlatformClient(ABC):
    """Uniform interface for interacting with a remote git hosting platform."""

    @abstractmethod
    async def list_issues(
        self, *, labels: list[str] | None = None, state: str = "open"
    ) -> Sequence[IssueData]: ...

    @abstractmethod
    async def get_issue(self, number: int) -> IssueData: ...

    @abstractmethod
    async def comment_on_issue(self, number: int, body: str) -> None: ...

    @abstractmethod
    async def create_pull_request(
        self,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> PRData: ...

    @abstractmethod
    async def close_issue(self, number: int) -> None: ...
