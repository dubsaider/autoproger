"""Hybrid trigger adapters to unified RunRequest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from state.models import RunRequest


@dataclass(slots=True)
class ManualTrigger:
    repo_path: str
    repo_slug: str = ""

    def to_request(self, text: str) -> RunRequest:
        return RunRequest(
            source="manual",
            text=text,
            repo_path=self.repo_path,
            repo_slug=self.repo_slug,
        )


@dataclass(slots=True)
class GitHubEventTrigger:
    repo_path: str

    def from_payload(self, event_type: str, payload: dict[str, Any]) -> RunRequest:
        repo = payload.get("repository", {})
        issue = payload.get("issue", {})
        comment = payload.get("comment", {})
        text = comment.get("body") or issue.get("body") or issue.get("title") or ""
        return RunRequest(
            source="github_event",
            text=text,
            repo_path=self.repo_path,
            repo_slug=repo.get("full_name", ""),
            issue_id=str(issue.get("number", "")),
            metadata={
                "event_type": event_type,
                "raw_payload": payload,
            },
        )

    def from_file(self, event_type: str, payload_file: str | Path) -> RunRequest:
        payload = json.loads(Path(payload_file).read_text(encoding="utf-8"))
        return self.from_payload(event_type, payload)
