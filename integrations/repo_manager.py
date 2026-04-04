"""Local repository operations: clone, branch, commit, push."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from git import Repo

from core.config import get_settings
from core.models import FileChange

log = logging.getLogger(__name__)


class RepoManager:
    """Manages a local clone of a remote repository."""

    def __init__(self, repo_url: str, token: str, *, workdir: Path | None = None) -> None:
        self._repo_url = repo_url
        self._token = token
        self._workdir = workdir or get_settings().workdir_abs
        self._local_path: Path | None = None
        self._repo: Repo | None = None

    @property
    def local_path(self) -> Path:
        if self._local_path is None:
            raise RuntimeError("Repository not cloned yet — call clone() first")
        return self._local_path

    @property
    def repo(self) -> Repo:
        if self._repo is None:
            raise RuntimeError("Repository not cloned yet — call clone() first")
        return self._repo

    def _authenticated_url(self) -> str:
        url = self._repo_url
        if self._token and "://" in url:
            scheme, rest = url.split("://", 1)
            url = f"{scheme}://x-access-token:{self._token}@{rest}"
        return url

    def clone(self, *, branch: str = "main") -> Path:
        slug = self._repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        dest = self._workdir / slug
        if dest.exists():
            log.info("Reusing existing clone at %s", dest)
            self._repo = Repo(dest)
            self._local_path = dest
            origin = self._repo.remotes.origin
            origin.fetch()
            self._repo.git.checkout(branch)
            self._repo.git.reset("--hard", f"origin/{branch}")
            return dest

        log.info("Cloning %s -> %s", self._repo_url, dest)
        self._repo = Repo.clone_from(self._authenticated_url(), dest, branch=branch)
        self._local_path = dest
        return dest

    def create_branch(self, branch_name: str) -> None:
        self.repo.git.checkout("-b", branch_name)
        log.info("Created and switched to branch %s", branch_name)

    def apply_changes(self, changes: list[FileChange]) -> list[str]:
        modified: list[str] = []
        for change in changes:
            file_path = self.local_path / change.path
            if change.action == "delete":
                if file_path.exists():
                    file_path.unlink()
                    modified.append(change.path)
            elif change.action in ("create", "modify"):
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(change.content or "", encoding="utf-8")
                modified.append(change.path)
        return modified

    def get_diff(self) -> str:
        """Return the diff of all uncommitted changes (staged + unstaged)."""
        return self.repo.git.diff("HEAD")

    def get_changed_files(self) -> list[str]:
        """Return list of paths with uncommitted changes."""
        status = self.repo.git.status("--porcelain")
        files = []
        for line in status.strip().splitlines():
            if line.strip():
                files.append(line[3:].strip())
        return files

    def stage_all(self) -> None:
        """Stage all changes (including untracked files)."""
        self.repo.git.add("-A")

    def commit(self, message: str) -> str:
        self.repo.git.add("-A")
        self.repo.index.commit(message)
        sha = self.repo.head.commit.hexsha[:8]
        log.info("Committed %s: %s", sha, message)
        return sha

    def push(self, branch_name: str) -> None:
        origin = self.repo.remotes.origin
        origin.set_url(self._authenticated_url())
        origin.push(branch_name)
        log.info("Pushed branch %s", branch_name)

    def cleanup(self) -> None:
        if self._local_path and self._local_path.exists():
            shutil.rmtree(self._local_path, ignore_errors=True)
            log.info("Cleaned up %s", self._local_path)
