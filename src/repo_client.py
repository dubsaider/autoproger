"""Клиент для работы с репозиторием (GitHub)."""
from typing import Protocol

from src.models import Issue


class RepoClient(Protocol):
    """Интерфейс клиента репозитория."""

    def list_open_issues(self, labels: list[str] | None = None) -> list[Issue]:
        ...

    def get_issue(self, number: int) -> Issue | None:
        ...

    def create_branch(self, branch_name: str, from_ref: str = "main") -> bool:
        ...

    def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        draft: bool = True,
    ) -> str:
        """Возвращает URL созданного PR/MR."""
        ...

    def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> Issue | None:
        ...


def _issue_from_github(gh_issue) -> Issue:
    return Issue(
        number=gh_issue.number,
        title=gh_issue.title,
        body=gh_issue.body or "",
        labels=[lb.name for lb in (gh_issue.labels or [])],
        state=gh_issue.state,
        html_url=gh_issue.html_url,
        raw=gh_issue,
    )


class GitHubRepoClient:
    """Клиент для GitHub через PyGithub."""

    def __init__(self, owner: str, repo_name: str, token: str):
        from github import Github
        self._gh = Github(token)
        self._repo = self._gh.get_repo(f"{owner}/{repo_name}")
        self._owner = owner
        self._name = repo_name

    def list_open_issues(self, labels: list[str] | None = None) -> list[Issue]:
        kwargs = {"state": "open"}
        if labels:
            kwargs["labels"] = labels
        issues = self._repo.get_issues(**kwargs)
        return [_issue_from_github(i) for i in issues if not i.pull_request]

    def get_issue(self, number: int) -> Issue | None:
        try:
            gh_issue = self._repo.get_issue(number)
            return _issue_from_github(gh_issue)
        except Exception:
            return None

    def create_branch(self, branch_name: str, from_ref: str = "main") -> bool:
        try:
            base = self._repo.get_branch(from_ref)
            self._repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=base.commit.sha,
            )
            return True
        except Exception:
            return False

    def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        draft: bool = True,
    ) -> str:
        pr = self._repo.create_pull(
            title=title,
            body=body,
            head=head,
            base=base,
            draft=draft,
        )
        return pr.html_url

    def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> Issue | None:
        kwargs = {"title": title, "body": body}
        if labels:
            kwargs["labels"] = labels
        try:
            gh_issue = self._repo.create_issue(**kwargs)
            return _issue_from_github(gh_issue)
        except Exception as first_error:
            # Частый кейс: часть labels не существует в репозитории.
            # Пробуем создать issue без labels, чтобы не терять сам issue.
            if labels:
                try:
                    gh_issue = self._repo.create_issue(title=title, body=body)
                    return _issue_from_github(gh_issue)
                except Exception as second_error:
                    raise RuntimeError(
                        f"GitHub create_issue failed with labels ({first_error}) and without labels ({second_error})"
                    )
            raise RuntimeError(f"GitHub create_issue failed: {first_error}")


class GitLabRepoClient:
    """Клиент для GitLab (в т.ч. self-hosted)."""

    def __init__(self, url: str, project_id: int | str, token: str):
        import gitlab
        self._gl = gitlab.Gitlab(url, private_token=token)
        self._gl.auth()
        self._project = self._gl.projects.get(project_id)
        self._project_id = project_id

    def list_open_issues(self, labels: list[str] | None = None) -> list[Issue]:
        params = {"state": "opened"}
        if labels:
            params["labels"] = labels
        issues = self._project.issues.list(**params)
        return [
            Issue(
                number=i.iid,
                title=i.title,
                body=i.description or "",
                labels=i.labels or [],
                state=i.state,
                html_url=i.web_url,
                raw=i,
            )
            for i in issues
        ]

    def get_issue(self, number: int) -> Issue | None:
        try:
            i = self._project.issues.get(number)
            return Issue(
                number=i.iid,
                title=i.title,
                body=i.description or "",
                labels=i.labels or [],
                state=i.state,
                html_url=i.web_url,
                raw=i,
            )
        except Exception:
            return None

    def create_branch(self, branch_name: str, from_ref: str = "main") -> bool:
        try:
            self._project.branches.create({"branch": branch_name, "ref": from_ref})
            return True
        except Exception:
            return False

    def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        draft: bool = True,
    ) -> str:
        mr = self._project.mergerequests.create(
            {
                "source_branch": head,
                "target_branch": base,
                "title": title,
                "description": body,
            }
        )
        if draft and hasattr(mr, "draft"):
            mr.draft = True
            mr.save()
        return mr.web_url

    def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> Issue | None:
        payload = {"title": title, "description": body}
        if labels:
            payload["labels"] = labels
        try:
            i = self._project.issues.create(payload)
            return Issue(
                number=i.iid,
                title=i.title,
                body=i.description or "",
                labels=i.labels or [],
                state=i.state,
                html_url=i.web_url,
                raw=i,
            )
        except Exception as first_error:
            if labels:
                try:
                    i = self._project.issues.create({"title": title, "description": body})
                    return Issue(
                        number=i.iid,
                        title=i.title,
                        body=i.description or "",
                        labels=i.labels or [],
                        state=i.state,
                        html_url=i.web_url,
                        raw=i,
                    )
                except Exception as second_error:
                    raise RuntimeError(
                        f"GitLab create_issue failed with labels ({first_error}) and without labels ({second_error})"
                    )
            raise RuntimeError(f"GitLab create_issue failed: {first_error}")
