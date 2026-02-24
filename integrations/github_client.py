"""Minimal GitHub API client for PR and event payload handling."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass(slots=True)
class GitHubConfig:
    token: str
    owner: str
    repo: str
    api_url: str = "https://api.github.com"


class GitHubClient:
    def __init__(self, config: GitHubConfig) -> None:
        self.config = config

    def create_pull_request(
        self,
        *,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        draft: bool = True,
    ) -> str:
        url = f"{self.config.api_url}/repos/{self.config.owner}/{self.config.repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "draft": draft,
        }
        response = self._request("POST", url, json=payload)
        return str(response.get("html_url", ""))

    def parse_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Normalizes GitHub webhook payload into run request metadata."""
        repo = payload.get("repository", {})
        issue = payload.get("issue", {})
        comment = payload.get("comment", {})
        return {
            "source": "github_event",
            "event_type": event_type,
            "repo_slug": repo.get("full_name", ""),
            "issue_id": str(issue.get("number", "")),
            "text": comment.get("body") or issue.get("title") or "",
            "metadata": payload,
        }

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.config.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        payload = kwargs.get("json")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url=url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API error {exc.code}: {body}") from exc
