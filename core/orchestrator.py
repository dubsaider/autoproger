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

log = logging.getLogger(__name__)

MAX_REVIEW_ROUNDS = 2


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

        # 1. Clone repo
        rm = RepoManager(repo_cfg.url, repo_cfg.token)
        rm.clone(branch=repo_cfg.default_branch)

        # For non-agentic providers, build context from the repo
        context = ""
        if not is_agentic:
            idx = index_repo(rm.local_path)
            context = build_context_prompt(
                rm.local_path, idx,
                issue_title=task.issue_title,
                issue_body=task.issue_body,
            )

        # 2. Planning
        planner = PlannerAgent(provider)
        plan_result = await planner.run(
            context=context,
            issue_title=task.issue_title,
            issue_body=task.issue_body,
            cwd=rm.local_path if is_agentic else None,
        )
        run.agent_results.append(plan_result)
        if not plan_result.success:
            await self._finish_run(run, TaskStatus.FAILED, run.agent_results)
            await self._update_task(task.id, TaskStatus.FAILED)
            return run

        plan = plan_result.output
        log.info("Plan: %s", plan.get("summary", "N/A"))

        if self._on_plan_ready:
            await self._on_plan_ready(task, plan)

        # 3. Create working branch
        branch_name = f"{repo_cfg.branch_prefix}{task.issue_number}-{_slug(task.issue_title)}"
        rm.create_branch(branch_name)

        # 4. Development
        if is_agentic:
            run = await self._develop_agentic(
                provider, rm, plan, task, run, context, repo_cfg, branch_name
            )
        else:
            run = await self._develop_completion(
                provider, rm, plan, task, run, context, repo_cfg, branch_name
            )

        if run.status == TaskStatus.FAILED:
            return run

        # 5. Quality gates
        quality = await run_quality_gates(rm.local_path)

        # 6. Commit, push, PR
        commit_msg = plan.get("commit_message") or f"feat: resolve #{task.issue_number}"
        rm.commit(commit_msg)
        rm.push(branch_name)

        pr_body = self._build_pr_body(task, plan, quality, run)
        pr = await platform_client.create_pull_request(
            title=f"[autoproger] {task.issue_title}",
            body=pr_body,
            head=branch_name,
            base=repo_cfg.default_branch,
        )

        run.pr_url = pr.url
        run.branch_name = branch_name
        await self._finish_run(run, TaskStatus.COMPLETED, run.agent_results, pr.url, branch_name)
        await self._update_task(task.id, TaskStatus.COMPLETED)

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
    ) -> Run:
        """Developer edits files directly via Claude Code, reviewer checks the diff."""

        developer = DeveloperAgent(provider)
        dev_result = await developer.run(plan=plan, cwd=rm.local_path)
        run.agent_results.append(dev_result)
        if not dev_result.success:
            await self._finish_run(run, TaskStatus.FAILED, run.agent_results)
            await self._update_task(task.id, TaskStatus.FAILED)
            return run

        dev_session_id = dev_result.output.get("session_id")

        # Get diff of what Claude Code changed
        diff = rm.get_diff()
        if not diff.strip():
            log.warning("Developer agent made no changes")
            await self._finish_run(run, TaskStatus.FAILED, run.agent_results)
            await self._update_task(task.id, TaskStatus.FAILED)
            return run

        # Review loop
        reviewer = ReviewerAgent(provider)
        for round_num in range(MAX_REVIEW_ROUNDS):
            review_result = await reviewer.run(
                plan=plan, diff=diff, cwd=rm.local_path
            )
            run.agent_results.append(review_result)

            if review_result.output.get("approved", False):
                break

            critical = [
                i for i in review_result.output.get("issues", [])
                if i.get("severity") == "critical"
            ]
            if not critical:
                break

            # Re-run developer with review feedback, resuming its session
            dev_result = await developer.run(
                plan={**plan, "review_feedback": review_result.output.get("issues", [])},
                cwd=rm.local_path,
                session_id=dev_session_id,
            )
            run.agent_results.append(dev_result)
            dev_session_id = dev_result.output.get("session_id", dev_session_id)
            diff = rm.get_diff()

        # Tester
        tester = TesterAgent(provider)
        test_result = await tester.run(diff=diff, cwd=rm.local_path)
        run.agent_results.append(test_result)

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
