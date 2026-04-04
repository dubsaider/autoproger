"""Fake/mock implementations of external dependencies for testing.

- FakeLLMProvider: returns deterministic JSON responses, no real LLM calls
- FakeGitPlatformClient: records calls, no real GitHub/GitLab API
- create_local_repo(): creates a bare + working git repo in a temp dir
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Sequence

from git import Repo

from core.models import LLMMessage, LLMResponse, ToolDefinition
from integrations.base import GitPlatformClient, IssueData, PRData
from llm.base import LLMProvider


# ---------------------------------------------------------------------------
# Canned responses for each agent role
# ---------------------------------------------------------------------------

PLANNER_RESPONSE = json.dumps({
    "summary": "Add greeting module with hello() function",
    "steps": [
        {
            "description": "Create greeting.py with hello() function",
            "files": ["greeting.py"],
            "action": "create",
        },
        {
            "description": "Create README.md",
            "files": ["README.md"],
            "action": "create",
        },
    ],
    "dependencies": [],
    "risks": [],
    "estimated_complexity": "low",
})

DEVELOPER_RESPONSE = json.dumps({
    "changes": [
        {
            "path": "greeting.py",
            "action": "create",
            "content": 'def hello(name: str = "World") -> str:\n    return f"Hello, {name}!"\n',
            "explanation": "New greeting module",
        },
        {
            "path": "README.md",
            "action": "create",
            "content": "# Test Project\n\nA simple greeting module.\n",
            "explanation": "Add README",
        },
    ],
    "commit_message": "feat: add greeting module",
})

REVIEWER_RESPONSE = json.dumps({
    "approved": True,
    "issues": [],
    "summary": "Code looks clean, approved.",
})

TESTER_RESPONSE = json.dumps({
    "test_files": [
        {
            "path": "tests/test_greeting.py",
            "content": (
                "from greeting import hello\n\n"
                "def test_hello_default():\n"
                '    assert hello() == "Hello, World!"\n\n'
                "def test_hello_name():\n"
                '    assert hello("Alice") == "Hello, Alice!"\n'
            ),
            "description": "Unit tests for greeting.hello()",
        },
    ],
    "test_command": "pytest tests/",
    "coverage_notes": "Covers default and named greetings",
})


def _detect_agent(messages: list[LLMMessage]) -> str:
    """Determine which agent is calling based on the system prompt."""
    system = ""
    for m in messages:
        if m.role == "system":
            system = m.content.lower()
            break

    if "architect" in system:
        return "planner"
    if "reviewer" in system or "review" in system:
        return "reviewer"
    if "qa" in system or "test" in system:
        return "tester"
    return "developer"


# ---------------------------------------------------------------------------
# FakeLLMProvider
# ---------------------------------------------------------------------------

class FakeLLMProvider(LLMProvider):
    """Returns canned JSON responses based on which agent is calling.

    Records all calls for later assertions.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

    @property
    def model_name(self) -> str:
        return "fake-model"

    @property
    def max_context_tokens(self) -> int:
        return 200_000

    @property
    def supports_tools(self) -> bool:
        return False

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        agent = _detect_agent(messages)
        self.calls.append({"agent": agent, "messages": len(messages)})

        responses = {
            "planner": PLANNER_RESPONSE,
            "developer": DEVELOPER_RESPONSE,
            "reviewer": REVIEWER_RESPONSE,
            "tester": TESTER_RESPONSE,
        }
        content = responses.get(agent, '{"raw": "unknown agent"}')

        return LLMResponse(
            content=content,
            tokens_input=100,
            tokens_output=200,
            model="fake-model",
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        resp = await self.complete(messages, temperature=temperature, max_tokens=max_tokens)
        yield resp.content


# ---------------------------------------------------------------------------
# FakeGitPlatformClient
# ---------------------------------------------------------------------------

@dataclass
class FakeGitPlatformClient(GitPlatformClient):
    """Records PR creation and other calls without touching any real API."""

    created_prs: list[PRData] = field(default_factory=list)
    comments: list[tuple[int, str]] = field(default_factory=list)
    closed_issues: list[int] = field(default_factory=list)
    _pr_counter: int = 0

    async def list_issues(
        self, *, labels: list[str] | None = None, state: str = "open"
    ) -> Sequence[IssueData]:
        return []

    async def get_issue(self, number: int) -> IssueData:
        return IssueData(
            number=number,
            title=f"Test issue #{number}",
            body="Test body",
            labels=["autoproger"],
            state="open",
            url=f"https://fake.git/issues/{number}",
        )

    async def comment_on_issue(self, number: int, body: str) -> None:
        self.comments.append((number, body))

    async def create_pull_request(
        self, *, title: str, body: str, head: str, base: str
    ) -> PRData:
        self._pr_counter += 1
        pr = PRData(
            number=self._pr_counter,
            title=title,
            body=body,
            url=f"https://fake.git/pull/{self._pr_counter}",
            state="open",
            branch=head,
        )
        self.created_prs.append(pr)
        return pr

    async def close_issue(self, number: int) -> None:
        self.closed_issues.append(number)


# ---------------------------------------------------------------------------
# Local git repo for testing (no remote network calls)
# ---------------------------------------------------------------------------

def create_local_repo(base_dir: Path | None = None) -> tuple[Path, Path, str]:
    """Create a bare 'remote' repo and a seeded working copy.

    Returns (bare_repo_path, work_dir, file_url).
    The file_url can be passed as repo_url to RepoManager.
    """
    base = base_dir or Path(tempfile.mkdtemp(prefix="autoproger_test_"))

    bare_path = base / "remote.git"
    bare_path.mkdir(parents=True)
    Repo.init(bare_path, bare=True)

    work_path = base / "work"
    repo = Repo.clone_from(str(bare_path), str(work_path))

    # Seed with initial commit so we have a branch
    seed_file = work_path / "seed.txt"
    seed_file.write_text("Initial seed file for testing.\n", encoding="utf-8")
    repo.index.add(["seed.txt"])
    repo.index.commit("Initial commit")
    repo.remotes.origin.push("master")

    # The default branch after init is 'master'; rename to 'main' for consistency
    repo.git.branch("-m", "master", "main")
    repo.remotes.origin.push("main")

    file_url = bare_path.as_uri()  # file:///...
    return bare_path, work_path, file_url
