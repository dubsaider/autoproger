"""Main orchestrator: runs the full agent pipeline for a task.

Supports two execution paths:
1. Agentic (Claude Code): agents work directly on the cloned repo,
   changes are detected via git diff
2. Completion (API-based LLMs): agents return structured JSON,
   changes are applied programmatically
"""

from __future__ import annotations

import logging

from agents.developer import DeveloperAgent
from agents.planner import PlannerAgent
from agents.reviewer import ReviewerAgent
from agents.tester import TesterAgent
from context.builder import build_context_prompt
from context.indexer import index_repo
from core.models import (
    AgentResult,
    FileChange,
    RepoConfig,
    Run,
    Task,
    TaskStatus,
)
from integrations.base import GitPlatformClient
from integrations.repo_manager import RepoManager
from llm.router import LLMRouter
from quality.runner import run_quality_gates
from storage.database import async_session
from storage import repositories as repo_db
from core.progress import emit as _emit

log = logging.getLogger(__name__)

MAX_REVIEW_ROUNDS = 1


class Orchestrator:
    def __init__(
        self,
        llm_router: LLMRouter,
        *,
        on_plan_ready: callable | None = None,
        on_pr_created: callable | None = None,
    ) -> None:
        self._llm = llm_router
        self._on_plan_ready = on_plan_ready
        self._on_pr_created = on_pr_created

    async def execute(
        self,
        task: Task,
        repo_cfg: RepoConfig,
        platform_client: GitPlatformClient,
    ) -> Run:
        run = Run(task_id=task.id)
        async with async_session() as session:
            await repo_db.create_run(session, id=run.id, task_id=run.task_id)

        try:
            await self._update_task(task.id, TaskStatus.IN_PROGRESS)
            result = await self._run_pipeline(task, repo_cfg, platform_client, run)
            return result
        except Exception:
            log.exception("Pipeline failed for task %s", task.id)
            await self._finish_run(run, TaskStatus.FAILED, run.agent_results)
            await self._update_task(task.id, TaskStatus.FAILED)
            raise

    async def _run_pipeline(
        self,
        task: Task,
        repo_cfg: RepoConfig,
        platform_client: GitPlatformClient,
        run: Run,
    ) -> Run:
        provider = self._llm.get(repo_cfg.llm_provider)
        is_agentic = provider.supports_agentic
        rid = run.id

        # Load checkpoint
        async with async_session() as session:
            checkpoint = await repo_db.get_checkpoint(session, task.id)
        if checkpoint:
            # Validate checkpoint plan — if it's just a raw text blob, discard it
            cp_plan = checkpoint.get("plan", {})
            if cp_plan and set(cp_plan.keys()) <= {"raw", "num_turns", "cost_usd", "session_id"}:
                log.warning("Checkpoint plan is malformed (raw only) — will re-run planner")
                checkpoint = {}
            else:
                _emit(rid, f"Resuming from checkpoint: stage={checkpoint.get('stage', '?')}", level="info")

        # 1. Clone repo
        _emit(rid, f"Cloning repository {repo_cfg.url}...")
        rm = RepoManager(repo_cfg.url, repo_cfg.token)
        rm.clone(branch=repo_cfg.default_branch, task_id=task.id)
        _emit(rid, "Repository ready", level="success")

        # For non-agentic providers, build context from the repo
        context = ""
        if not is_agentic:
            _emit(rid, "Building context index...")
            idx = index_repo(rm.local_path)
            context = build_context_prompt(
                rm.local_path, idx,
                issue_title=task.issue_title,
                issue_body=task.issue_body,
            )

        # 2. Planning — skip if checkpoint has plan
        if checkpoint.get("stage") in ("developer", "review", "tester", "done") and checkpoint.get("plan"):
            plan = checkpoint["plan"]
            _emit(rid, f"Skipping planner (checkpoint): {plan.get('summary', 'N/A')}", agent="planner", level="success")
        else:
            _emit(rid, "Analyzing codebase and creating implementation plan...", agent="planner")
            planner = PlannerAgent(provider)
            plan_result = await planner.run(
                context=context,
                issue_title=task.issue_title,
                issue_body=task.issue_body,
                cwd=rm.local_path if is_agentic else None,
            )
            run.agent_results.append(plan_result)
            await self._save_run_progress(run)
            if not plan_result.success:
                _emit(rid, f"Planner failed: {plan_result.error}", agent="planner", level="error")
                await self._finish_run(run, TaskStatus.FAILED, run.agent_results)
                await self._update_task(task.id, TaskStatus.FAILED)
                return run

            plan = plan_result.output
            _emit(rid, f"Plan ready: {plan.get('summary', 'N/A')}", agent="planner", level="success")
            complexity = plan.get("estimated_complexity", "")
            if complexity:
                _emit(rid, f"Complexity: {complexity}", agent="planner", level="info")
            for i, step in enumerate(plan.get("steps", [])[:8], 1):
                files = ", ".join(step.get("files", [])[:3])
                suffix = f" ({files})" if files else ""
                _emit(rid, f"  Step {i}: {step.get('description', '')}{suffix}", agent="planner", level="info")
            risks = plan.get("risks", [])
            if risks:
                _emit(rid, f"Risks: {'; '.join(risks[:3])}", agent="planner", level="warning")
            log.info("Plan: %s", plan.get("summary", "N/A"))

            # Save checkpoint after planning
            async with async_session() as session:
                await repo_db.save_checkpoint(session, task.id, {"stage": "developer", "plan": plan})

        if self._on_plan_ready:
            await self._on_plan_ready(task, plan)

        # 3. Create working branch
        branch_name = f"{repo_cfg.branch_prefix}{task.issue_number}-{_slug(task.issue_title)}"
        rm.create_branch(branch_name)
        _emit(rid, f"Created branch: {branch_name}")

        # 4. Development
        if is_agentic:
            run = await self._develop_agentic(
                provider, rm, plan, task, run, context, repo_cfg, branch_name,
                checkpoint=checkpoint,
            )
        else:
            run = await self._develop_completion(
                provider, rm, plan, task, run, context, repo_cfg, branch_name
            )

        if run.status == TaskStatus.FAILED:
            return run

        # 5. Quality gates
        _emit(rid, "Running quality gates...")
        quality = await run_quality_gates(rm.local_path)
        _emit(rid, f"Quality gates: {quality.summary}")

        # 6. Commit, push, PR
        commit_msg = plan.get("commit_message") or f"feat: resolve #{task.issue_number}"
        _emit(rid, f"Committing: {commit_msg}")
        rm.commit(commit_msg)
        rm.push(branch_name)
        _emit(rid, "Pushed to remote", level="success")

        pr_body = self._build_pr_body(task, plan, quality, run)
        pr = await platform_client.create_pull_request(
            title=f"[autoproger] {task.issue_title}",
            body=pr_body,
            head=branch_name,
            base=repo_cfg.default_branch,
        )

        _emit(rid, "Creating Pull Request...")
        run.pr_url = pr.url
        run.branch_name = branch_name
        await self._finish_run(run, TaskStatus.COMPLETED, run.agent_results, pr.url, branch_name)
        await self._update_task(task.id, TaskStatus.COMPLETED)
        # Clear checkpoint on success
        async with async_session() as session:
            await repo_db.clear_checkpoint(session, task.id)
        _emit(rid, f"PR created: {pr.url}", level="success")

        if self._on_pr_created:
            await self._on_pr_created(task, pr)

        log.info("Pipeline complete: PR %s for task %s", pr.url, task.id)
        return run

    # ------------------------------------------------------------------
    # Agentic path (Claude Code)
    # ------------------------------------------------------------------

    async def _develop_agentic(
        self, provider, rm: RepoManager, plan: dict, task: Task,
        run: Run, context: str, repo_cfg: RepoConfig, branch_name: str,
        checkpoint: dict | None = None,
    ) -> Run:
        """Developer edits files directly via Claude Code, reviewer checks the diff."""
        rid = run.id

        # If checkpoint has a saved diff, apply it directly — no need to re-run developer
        saved_diff = (checkpoint or {}).get("diff", "")
        if saved_diff:
            _emit(rid, "Restoring changes from checkpoint (skipping developer)...", agent="developer", level="info")
            try:
                rm.apply_diff(saved_diff)
                diff = rm.get_diff()
                if diff.strip():
                    _emit(rid, "Checkpoint diff applied ✓", agent="developer", level="success")
                    diff_lines = diff.splitlines()
                    added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
                    removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
                    _emit(rid, f"Diff: +{added} / -{removed} lines", agent="developer", level="info")
                    dev_result = None  # skip developer agent
                    dev_session_id = (checkpoint or {}).get("dev_session_id")
                else:
                    _emit(rid, "Checkpoint diff applied but no changes detected — re-running developer", agent="developer", level="warning")
                    saved_diff = ""  # fall through to developer
            except Exception as e:
                log.warning("Failed to apply checkpoint diff: %s — re-running developer", e)
                saved_diff = ""  # fall through to developer

        if not saved_diff:
            _emit(rid, "Implementing changes in the repository...", agent="developer")
            developer = DeveloperAgent(provider)
            dev_result = await developer.run(plan=plan, cwd=rm.local_path)
            run.agent_results.append(dev_result)
            await self._save_run_progress(run)
            if not dev_result.success:
                error_msg = dev_result.error or ""
                if "max_turns" in error_msg or "error_max_turns" in error_msg:
                    diff_check = rm.get_diff()
                    if diff_check.strip():
                        _emit(rid, "Developer hit turn limit but made changes — proceeding with review", agent="developer", level="warning")
                        dev_result = dev_result.model_copy(update={"success": True})
                        run.agent_results[-1] = dev_result
                    else:
                        _emit(rid, f"Developer hit turn limit with no changes: {error_msg}", agent="developer", level="error")
                        await self._finish_run(run, TaskStatus.FAILED, run.agent_results)
                        await self._update_task(task.id, TaskStatus.FAILED)
                        return run
                elif "limit" in error_msg.lower():
                    _emit(rid, f"Developer stopped by rate/budget limit: {error_msg}", agent="developer", level="error")
                    await self._finish_run(run, TaskStatus.FAILED, run.agent_results)
                    await self._update_task(task.id, TaskStatus.FAILED)
                    return run
                else:
                    _emit(rid, f"Developer failed: {error_msg}", agent="developer", level="error")
                    await self._finish_run(run, TaskStatus.FAILED, run.agent_results)
                    await self._update_task(task.id, TaskStatus.FAILED)
                    return run
            _emit(rid, "Developer finished implementing changes", agent="developer", level="success")

            dev_session_id = dev_result.output.get("session_id")

            # Get diff of what Claude Code changed
            diff = rm.get_diff()
            if not diff.strip():
                log.warning("Developer agent made no changes")
                _emit(rid, "No changes detected after development", agent="developer", level="warning")
                await self._finish_run(run, TaskStatus.FAILED, run.agent_results)
                await self._update_task(task.id, TaskStatus.FAILED)
                return run

            # Save checkpoint — include diff so restart skips re-running developer
            async with async_session() as session:
                await repo_db.save_checkpoint(session, task.id, {
                    "stage": "review",
                    "plan": plan,
                    "dev_session_id": dev_session_id,
                    "diff": diff,
                })

        # Emit diff statistics
        diff_lines = diff.splitlines()
        added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
        changed_files = rm.get_changed_files()
        _emit(rid, f"Diff: {len(changed_files)} files changed, +{added} / -{removed} lines", agent="developer", level="info")
        for f in changed_files[:10]:
            _emit(rid, f"  ✎ {f}", agent="developer", level="info")

        # Review loop
        reviewer = ReviewerAgent(provider)
        for round_num in range(MAX_REVIEW_ROUNDS):
            _emit(rid, f"Reviewing changes (round {round_num + 1})...", agent="reviewer")
            review_result = await reviewer.run(
                plan=plan, diff=diff, cwd=rm.local_path
            )
            run.agent_results.append(review_result)
            await self._save_run_progress(run)

            review_summary = review_result.output.get("summary", "")
            if review_summary:
                _emit(rid, f"Review summary: {review_summary}", agent="reviewer", level="info")

            all_issues = review_result.output.get("issues", [])
            for issue in all_issues[:10]:
                sev = issue.get("severity", "?")
                lvl = "error" if sev == "critical" else "warning" if sev == "warning" else "info"
                file_info = f"[{issue.get('file', '?')}] " if issue.get("file") else ""
                _emit(rid, f"  [{sev}] {file_info}{issue.get('description', '')}", agent="reviewer", level=lvl)

            if review_result.output.get("approved", False):
                _emit(rid, "Code review approved ✓", agent="reviewer", level="success")
                break

            critical = [i for i in all_issues if i.get("severity") == "critical"]
            if not critical:
                _emit(rid, "No critical issues found, proceeding", agent="reviewer", level="success")
                break

            _emit(rid, f"Found {len(critical)} critical issues, requesting fixes...", agent="reviewer", level="warning")
            dev_result = await developer.run(
                plan={**plan, "review_feedback": review_result.output.get("issues", [])},
                cwd=rm.local_path,
                session_id=dev_session_id,
            )
            run.agent_results.append(dev_result)
            await self._save_run_progress(run)
            dev_session_id = dev_result.output.get("session_id", dev_session_id)
            diff = rm.get_diff()

        # Tester — pass both the live diff and the last-commit diff as fallback
        # so tester always has context even after commit/restart
        tester_diff = diff.strip() or rm.get_last_commit_diff()

        # Skip tester if all changed files are config/yaml/docs only (nothing to unit-test)
        if _is_config_only_diff(tester_diff):
            _emit(rid, "Skipping tester: only config/YAML/Markdown files changed", agent="tester", level="info")
        else:
            _emit(rid, "Writing tests for the changes...", agent="tester")
            tester = TesterAgent(provider)
            test_result = await tester.run(diff=tester_diff, cwd=rm.local_path)
            run.agent_results.append(test_result)
            await self._save_run_progress(run)
            if test_result.success:
                test_summary = test_result.output.get("summary") or test_result.output.get("raw", "")
                if test_summary:
                    short = test_summary[:200]
                    _emit(rid, f"Tests: {short}", agent="tester", level="success")
                else:
                    _emit(rid, "Tests written ✓", agent="tester", level="success")
                for tf in test_result.output.get("test_files", [])[:5]:
                    _emit(rid, f"  + {tf.get('path', '?')}", agent="tester", level="info")
            else:
                _emit(rid, f"Tester: {test_result.error}", agent="tester", level="warning")

        return run

    # ------------------------------------------------------------------
    # Completion path (API-based LLMs)
    # ------------------------------------------------------------------

    async def _develop_completion(
        self, provider, rm: RepoManager, plan: dict, task: Task,
        run: Run, context: str, repo_cfg: RepoConfig, branch_name: str,
    ) -> Run:
        """Developer returns JSON changes, we apply them programmatically."""

        developer = DeveloperAgent(provider)
        dev_result = await developer.run(context=context, plan=plan)
        run.agent_results.append(dev_result)
        if not dev_result.success:
            await self._finish_run(run, TaskStatus.FAILED, run.agent_results)
            await self._update_task(task.id, TaskStatus.FAILED)
            return run

        changes = dev_result.output.get("changes", [])

        # Review loop
        reviewer = ReviewerAgent(provider)
        for round_num in range(MAX_REVIEW_ROUNDS):
            review_result = await reviewer.run(changes=changes, plan=plan)
            run.agent_results.append(review_result)

            if review_result.output.get("approved", False):
                break

            critical = [
                i for i in review_result.output.get("issues", [])
                if i.get("severity") == "critical"
            ]
            if not critical:
                break

            dev_result = await developer.run(context=context, plan={
                **plan,
                "review_feedback": review_result.output.get("issues", []),
            })
            run.agent_results.append(dev_result)
            if dev_result.success:
                changes = dev_result.output.get("changes", changes)

        # Tester
        tester = TesterAgent(provider)
        test_result = await tester.run(context=context, changes=changes)
        run.agent_results.append(test_result)
        if test_result.success:
            test_files = test_result.output.get("test_files", [])
            for tf in test_files:
                changes.append({
                    "path": tf["path"],
                    "action": "create",
                    "content": tf["content"],
                })

        # Apply changes to the repo
        file_changes = [
            FileChange(
                path=c["path"],
                action=c.get("action", "modify"),
                content=c.get("content"),
            )
            for c in changes[:repo_cfg.max_file_changes]
        ]
        rm.apply_changes(file_changes)

        return run

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_pr_body(task: Task, plan: dict, quality, run: Run) -> str:
        lines = [
            f"## Resolves #{task.issue_number}",
            "",
            f"**Issue:** {task.issue_title}",
            "",
            "### Plan",
            plan.get("summary", "N/A"),
            "",
            "### Quality gates",
            quality.summary,
            "",
            "### Agent pipeline",
        ]
        for r in run.agent_results:
            status = "OK" if r.success else "FAIL"
            lines.append(f"- **{r.role}**: {status} ({r.duration_ms}ms, {r.tokens_used} tokens)")
        lines.append("")
        lines.append("---")
        lines.append("*Generated by Autoproger v2 (Claude Code)*")
        return "\n".join(lines)

    @staticmethod
    async def _save_run_progress(run: Run) -> None:
        """Persist intermediate agent results to DB so frontend can poll them."""
        async with async_session() as session:
            await repo_db.update_run_results(
                session, run.id,
                agent_results=[r.model_dump() for r in run.agent_results],
            )

    @staticmethod
    async def _update_task(task_id: str, status: TaskStatus) -> None:
        async with async_session() as session:
            await repo_db.update_task_status(session, task_id, status)

    @staticmethod
    async def _finish_run(
        run: Run,
        status: TaskStatus,
        agent_results: list[AgentResult],
        pr_url: str | None = None,
        branch_name: str | None = None,
    ) -> None:
        run.status = status
        async with async_session() as session:
            await repo_db.finish_run(
                session,
                run.id,
                status=status,
                agent_results=[r.model_dump() for r in agent_results],
                pr_url=pr_url,
                branch_name=branch_name,
            )


def _slug(text: str, max_len: int = 30) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in text.lower())
    slug = slug.strip("-")[:max_len].rstrip("-")
    return slug or "task"


# Extensions where automated unit tests make no sense
_CONFIG_EXTENSIONS = {
    ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".env",
    ".md", ".rst", ".txt", ".json",
    ".gitignore", ".dockerignore", ".editorconfig",
    "dockerfile", "docker-compose",
}


def _is_config_only_diff(diff: str) -> bool:
    """Return True if every changed file in the diff is a config/docs file."""
    import re
    changed_files = re.findall(r"^diff --git a/\S+ b/(\S+)", diff, re.MULTILINE)
    if not changed_files:
        return False
    for path in changed_files:
        name = path.lower()
        ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
        base = name.rsplit("/", 1)[-1]
        is_config = (
            ext in _CONFIG_EXTENSIONS
            or any(kw in base for kw in ("dockerfile", "docker-compose", ".env"))
        )
        if not is_config:
            return False
    return True
