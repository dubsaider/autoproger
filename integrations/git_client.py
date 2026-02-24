"""Git lifecycle helpers for branch-per-run workflow."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class GitPolicy:
    base_branch: str = "main"
    branch_prefix: str = "auto"
    allow_main_writes: bool = False


class GitClient:
    def __init__(self, repo_path: Path | str, policy: GitPolicy | None = None) -> None:
        self.repo_path = Path(repo_path)
        self.policy = policy or GitPolicy()

    def make_branch_name(self, slug: str, ticket: str = "") -> str:
        date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        safe_slug = "-".join(part for part in slug.lower().split() if part)[:50]
        if ticket:
            return f"{self.policy.branch_prefix}/{ticket}-{safe_slug or 'task'}"
        return f"{self.policy.branch_prefix}/{date}-{safe_slug or 'task'}"

    def ensure_work_branch(self, branch_name: str) -> None:
        self._assert_not_main(branch_name)
        self._run(["git", "rev-parse", "--is-inside-work-tree"], check=True)
        self._run(["git", "fetch", "origin", self.policy.base_branch], check=False)
        try:
            self._run(
                ["git", "checkout", "-B", branch_name, f"origin/{self.policy.base_branch}"],
                check=True,
            )
            return
        except subprocess.CalledProcessError:
            # Fallback for repos without remote tracking branch.
            try:
                self._run(["git", "checkout", self.policy.base_branch], check=True)
                self._run(["git", "checkout", "-B", branch_name], check=True)
                return
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    f"Cannot create work branch from '{self.policy.base_branch}'. "
                    "Verify repo path and base branch."
                ) from exc

    def commit_all(self, message: str) -> bool:
        self._run(["git", "add", "-A"], check=True)
        status = self._run(["git", "status", "--porcelain"], check=True).stdout.strip()
        if not status:
            return False
        self._run(["git", "commit", "-m", message], check=True)
        return True

    def push_branch(self, branch_name: str) -> None:
        self._assert_not_main(branch_name)
        self._run(["git", "push", "-u", "origin", branch_name], check=True)

    def current_branch(self) -> str:
        return self._run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
        ).stdout.strip()

    def render_pr_body(self, template_path: Path, values: dict[str, str]) -> str:
        template = template_path.read_text(encoding="utf-8")
        body = template
        for key, value in values.items():
            body = body.replace(f"{{{{{key}}}}}", value)
        return body

    def _assert_not_main(self, branch_name: str) -> None:
        if self.policy.allow_main_writes:
            return
        forbidden = {"main", "master"}
        if branch_name in forbidden:
            raise RuntimeError("Direct changes to main/master are blocked by policy")

    def _run(self, cmd: Iterable[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(cmd),
            cwd=self.repo_path,
            check=check,
            capture_output=True,
            text=True,
        )
