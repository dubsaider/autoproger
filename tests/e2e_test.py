"""End-to-end pipeline test.

Verifies the full flow: issue -> task -> plan -> develop -> review -> test -> commit -> PR.

Uses FakeLLMProvider (no real LLM calls) and a local git repo (no network).
Can be run as:
  - pytest tests/e2e_test.py -v
  - python -m tests.e2e_test
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Configure env BEFORE any project imports (in-memory SQLite, fake provider)
# ---------------------------------------------------------------------------
_test_tmp = tempfile.mkdtemp(prefix="autoproger_e2e_")

os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["LLM_DEFAULT_PROVIDER"] = "anthropic"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["WORKDIR"] = str(Path(_test_tmp) / "workdir")

# ---------------------------------------------------------------------------
# Now import project modules
# ---------------------------------------------------------------------------
from core.config import get_settings                          # noqa: E402
from core.models import (                                     # noqa: E402
    Autonomy,
    Platform,
    RepoConfig,
    Task,
    TaskStatus,
)
from core.orchestrator import Orchestrator                    # noqa: E402
from core.task_manager import TaskManager                     # noqa: E402
from integrations.base import IssueData                       # noqa: E402
from llm.router import LLMRouter                              # noqa: E402
from storage.database import async_session, init_db           # noqa: E402
from storage import repositories as repo_db                   # noqa: E402

from tests.fakes import (                                     # noqa: E402
    FakeGitPlatformClient,
    FakeLLMProvider,
    create_local_repo,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers to reset module-level singletons between test runs
# ---------------------------------------------------------------------------

def _reset_db():
    import storage.database as db_mod
    if db_mod._engine is not None:
        # synchronous close is enough for teardown
        try:
            asyncio.get_event_loop().run_until_complete(db_mod._engine.dispose())
        except Exception:
            pass
    db_mod._engine = None
    db_mod._async_session = None


async def _dispose_engine():
    import storage.database as db_mod
    if db_mod._engine is not None:
        await db_mod._engine.dispose()
    db_mod._engine = None
    db_mod._async_session = None


def _reset_settings():
    import core.config as cfg_mod
    cfg_mod._settings = None


# ---------------------------------------------------------------------------
# The main end-to-end scenario
# ---------------------------------------------------------------------------

async def run_e2e() -> dict:
    """Execute the full pipeline and return a results dict for assertions."""
    results: dict = {}

    try:
        # 0. Reset singletons and init
        _reset_settings()
        import storage.database as db_mod
        db_mod._engine = None
        db_mod._async_session = None

        await init_db()
        log.info("[STEP 0] Database initialized (in-memory SQLite)")

        # 1. Create a local git repo (fake "remote")
        repo_base = Path(_test_tmp) / "repos"
        repo_base.mkdir(parents=True, exist_ok=True)
        bare_path, work_path, file_url = create_local_repo(repo_base)
        log.info("[STEP 1] Local git repo created: %s", file_url)
        results["repo_url"] = file_url

        # 2. Build LLM router with fake provider
        fake_llm = FakeLLMProvider()
        router = LLMRouter()
        router.register("fake", fake_llm, default=True)
        log.info("[STEP 2] FakeLLMProvider registered")

        # 3. Define repo config
        repo_cfg = RepoConfig(
            id="testrepo01",
            platform=Platform.GITHUB,
            url=file_url,
            token="",
            autonomy=Autonomy.FULL_AUTO,
            watch_labels=["autoproger"],
            branch_prefix="autoproger/",
            default_branch="main",
            llm_provider="fake",
        )

        async with async_session() as session:
            await repo_db.create_repo(
                session,
                id=repo_cfg.id,
                platform=repo_cfg.platform,
                url=repo_cfg.url,
                token=repo_cfg.token,
                autonomy=repo_cfg.autonomy,
                watch_labels=repo_cfg.watch_labels,
                branch_prefix=repo_cfg.branch_prefix,
                default_branch=repo_cfg.default_branch,
            )
        log.info("[STEP 3] RepoConfig persisted to DB")

        # 4. Simulate an incoming issue -> create task
        issue = IssueData(
            number=42,
            title="Add greeting module",
            body="Create a greeting.py file with a hello() function that accepts a name parameter.",
            labels=["autoproger"],
            state="open",
            url="https://fake.git/issues/42",
        )

        task_mgr = TaskManager()
        task = await task_mgr.create_task_from_issue(repo_cfg, issue)
        log.info("[STEP 4] Task created: %s (status=%s)", task.id, task.status)
        results["task_id"] = task.id
        results["task_initial_status"] = task.status

        assert task.status == TaskStatus.APPROVED, (
            f"Expected APPROVED for full_auto, got {task.status}"
        )

        # 5. Run orchestrator pipeline
        fake_platform = FakeGitPlatformClient()
        events: dict = {"plan_ready": False, "pr_created": False}

        async def on_plan_ready(t, plan):
            events["plan_ready"] = True
            events["plan_summary"] = plan.get("summary", "")
            log.info("[EVENT] Plan ready: %s", plan.get("summary", ""))

        async def on_pr_created(t, pr):
            events["pr_created"] = True
            events["pr_url"] = pr.url
            log.info("[EVENT] PR created: %s", pr.url)

        orchestrator = Orchestrator(
            router,
            on_plan_ready=on_plan_ready,
            on_pr_created=on_pr_created,
        )

        log.info("[STEP 5] Starting orchestrator pipeline...")
        run = await orchestrator.execute(task, repo_cfg, fake_platform)
        log.info("[STEP 5] Pipeline finished. Run status: %s", run.status)

        results["run_id"] = run.id
        results["run_status"] = run.status
        results["pr_url"] = run.pr_url
        results["branch_name"] = run.branch_name
        results["agent_results"] = [
            {"role": r.role, "success": r.success, "tokens": r.tokens_used}
            for r in run.agent_results
        ]
        results["events"] = events
        results["llm_calls"] = fake_llm.calls
        results["prs_created"] = len(fake_platform.created_prs)

        # 6. Verify DB state
        log.info("[STEP 6] Verifying DB state...")
        async with async_session() as session:
            db_task = await repo_db.get_task(session, task.id)
            db_run = await repo_db.get_run(session, run.id)

        results["db_task_status"] = db_task.status if db_task else "NOT_FOUND"
        results["db_run_status"] = db_run.status if db_run else "NOT_FOUND"
        results["db_run_pr_url"] = db_run.pr_url if db_run else None
        log.info("[STEP 6] DB: task=%s, run=%s", results["db_task_status"], results["db_run_status"])

        # 7. Verify git state
        log.info("[STEP 7] Verifying git state...")
        from git import Repo as GitRepo
        workdir = get_settings().workdir_abs
        cloned_dirs = [d for d in workdir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if cloned_dirs:
            cloned_repo = GitRepo(cloned_dirs[0])
            branches = [b.name for b in cloned_repo.branches]
            results["git_branches"] = branches

            files_in_repo = [
                str(f.relative_to(cloned_dirs[0]))
                for f in cloned_dirs[0].rglob("*")
                if f.is_file() and ".git" not in str(f)
            ]
            results["files_in_repo"] = files_in_repo
            log.info("[STEP 7] Git: branches=%s, files=%d", branches, len(files_in_repo))

    finally:
        await _dispose_engine()

    return results


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------

def verify_results(results: dict) -> list[str]:
    """Check the results dict and return a list of failures (empty = all passed)."""
    failures: list[str] = []

    def check(condition: bool, msg: str):
        if not condition:
            failures.append(msg)

    check(
        results.get("run_status") == TaskStatus.COMPLETED,
        f"Run status should be COMPLETED, got {results.get('run_status')}",
    )

    check(results.get("prs_created", 0) == 1, "Exactly one PR should be created")
    check(bool(results.get("pr_url")), "PR URL should be set")

    agent_results = results.get("agent_results", [])
    check(len(agent_results) >= 4, f"At least 4 agent results expected, got {len(agent_results)}")
    roles_seen = {r["role"] for r in agent_results}
    for role in ("planner", "developer", "reviewer", "tester"):
        check(role in roles_seen, f"Agent role '{role}' should have run")
    for r in agent_results:
        check(r["success"], f"Agent {r['role']} should have succeeded")

    check(results.get("events", {}).get("plan_ready"), "on_plan_ready callback should have fired")
    check(results.get("events", {}).get("pr_created"), "on_pr_created callback should have fired")

    check(len(results.get("llm_calls", [])) >= 4, "At least 4 LLM calls expected")

    check(
        results.get("db_task_status") == TaskStatus.COMPLETED,
        f"DB task status should be COMPLETED, got {results.get('db_task_status')}",
    )
    check(
        results.get("db_run_status") == TaskStatus.COMPLETED,
        f"DB run status should be COMPLETED, got {results.get('db_run_status')}",
    )
    check(bool(results.get("db_run_pr_url")), "DB run should have PR URL")

    branches = results.get("git_branches", [])
    check(
        any("autoproger/" in b for b in branches),
        f"A branch with 'autoproger/' prefix expected, got {branches}",
    )

    files = results.get("files_in_repo", [])
    check(
        any(f.endswith("greeting.py") for f in files),
        f"greeting.py should exist in repo, got {files}",
    )
    check(
        any(f.endswith("README.md") for f in files),
        f"README.md should exist in repo, got {files}",
    )
    check(
        any("test_greeting" in f for f in files),
        f"test_greeting.py should exist in repo, got {files}",
    )

    return failures


# ---------------------------------------------------------------------------
# pytest entry point
# ---------------------------------------------------------------------------

import pytest                                                 # noqa: E402


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    shutil.rmtree(_test_tmp, ignore_errors=True)


@pytest.mark.asyncio
async def test_full_pipeline_e2e():
    """End-to-end: issue -> task -> agents -> commit -> PR."""
    results = await run_e2e()

    failures = verify_results(results)
    if failures:
        detail = "\n".join(f"  - {f}" for f in failures)
        pytest.fail(f"E2E verification failed:\n{detail}")


# ---------------------------------------------------------------------------
# Standalone runner (python -m tests.e2e_test)
# ---------------------------------------------------------------------------

def _print_banner(text: str):
    w = 60
    print()
    print("=" * w)
    print(f"  {text}")
    print("=" * w)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
    )

    _print_banner("AUTOPROGER v2 -- End-to-End Pipeline Test")

    try:
        results = asyncio.run(run_e2e())
    except Exception as exc:
        print(f"\n{'!'*60}")
        print(f"  PIPELINE CRASHED: {exc}")
        print(f"{'!'*60}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
    finally:
        shutil.rmtree(_test_tmp, ignore_errors=True)

    _print_banner("RESULTS")
    for key in (
        "run_status", "pr_url", "branch_name",
        "prs_created", "db_task_status", "db_run_status",
    ):
        print(f"  {key}: {results.get(key)}")

    print("\n  Agent pipeline:")
    for r in results.get("agent_results", []):
        status = "OK" if r["success"] else "FAIL"
        print(f"    [{status}] {r['role']} ({r['tokens']} tokens)")

    print(f"\n  LLM calls: {len(results.get('llm_calls', []))}")
    print(f"  Git branches: {results.get('git_branches', [])}")
    print(f"  Files in repo: {results.get('files_in_repo', [])}")

    _print_banner("VERIFICATION")
    failures = verify_results(results)
    if failures:
        for f in failures:
            print(f"  FAIL: {f}")
        print(f"\n  {len(failures)} check(s) failed.")
        sys.exit(1)
    else:
        total_checks = 15
        print(f"  All {total_checks} checks passed.")
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
