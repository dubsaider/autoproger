"""CLI entrypoint for the new multi-agent GitOps orchestrator."""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from integrations.git_client import GitClient, GitPolicy
from integrations.github_client import GitHubClient, GitHubConfig
from integrations.triggers import GitHubEventTrigger, ManualTrigger
from orchestrator.security import sanitize_mapping
from orchestrator.workflow import Orchestrator, OrchestratorConfig
from state.models import QualityGate, Run, RunRequest, RunStatus, utc_now
from state.store import JSONStateStore
from workflows.quality_gates import QualityGateRunner


logger = logging.getLogger("autoproger.orchestrator")


@dataclass(slots=True)
class RuntimePolicy:
    max_retries: int = 3
    max_cycles: int = 20
    draft_pr: bool = True
    auto_merge: bool = False
    branch_prefix: str = "auto"
    base_branch: str = "main"
    local_only: bool = False


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='{"level":"%(levelname)s","message":"%(message)s","ts":"%(asctime)s"}',
    )


def run_request(
    request: RunRequest,
    policy: RuntimePolicy,
    *,
    state_dir: Path,
    dry_run: bool = False,
) -> Run:
    store = JSONStateStore(base_dir=state_dir)
    router_orchestrator = Orchestrator(
        state_store=store,
        config=OrchestratorConfig(retry_limit=policy.max_retries, dry_run=dry_run),
    )
    git = GitClient(
        request.repo_path,
        policy=GitPolicy(
            base_branch=policy.base_branch,
            branch_prefix=policy.branch_prefix,
            allow_main_writes=False,
        ),
    )

    branch_name = git.make_branch_name(
        slug=request.text[:80],
        ticket=request.issue_id,
    )
    run = router_orchestrator.start_run(request, branch_name=branch_name)
    try:
        store.write_artifact(run.id, "request.json", sanitize_mapping(request.metadata))
        logger.info("Preparing work branch %s", branch_name)
        git.ensure_work_branch(branch_name)
        logger.info("Run started %s", run.id)
        run = router_orchestrator.run_until_terminal(run, max_cycles=policy.max_cycles)
        if run.status != RunStatus.COMPLETED:
            logger.info("Run stopped with status %s", run.status.value)
            return run

        gate_runner = QualityGateRunner()
        gate_results = gate_runner.run_all(Path(request.repo_path))
        failed_gates = gate_runner.failed_gates(gate_results)
        for gate in gate_results:
            run.quality_gates.append(
                QualityGate(
                    id=f"{run.id}-{gate.name}",
                    run_id=run.id,
                    name=gate.name,
                    status=gate.status,
                    details=gate.output[:4000],
                    updated_at=utc_now(),
                )
            )
        store.write_artifact(
            run.id,
            "quality-gates.json",
            [asdict(gate) for gate in gate_results],
        )

        if failed_gates:
            run.status = RunStatus.FAILED
            run.last_error = f"Failed quality gates: {', '.join(failed_gates)}"
            store.save_run(run)
            return run

        if dry_run:
            store.save_run(run)
            return run

        committed = git.commit_all(f"auto: implement run {run.id}")
        if not committed:
            run.status = RunStatus.NEEDS_INPUT
            run.last_error = "No changes to commit in work branch"
            store.save_run(run)
            return run

        pr_body = git.render_pr_body(
            Path("templates/pull_request.md"),
            {
                "summary": run.outputs.get("summary", "Automated implementation cycle"),
                "changes": "See commit history in this branch",
                "test_plan": "Automated quality gates executed",
                "risks": "Review quality gate outputs before merge",
                "rollback": "Revert merge commit or close PR without merge",
            },
        )
        store.write_artifact(run.id, "pull_request.md", pr_body)
        if policy.local_only:
            run.outputs["local_only"] = True
            run.outputs["local_note"] = "Push and PR skipped by runtime policy"
            run.status = RunStatus.COMPLETED
            store.save_run(run)
            return run

        git.push_branch(run.branch_name)

        pr_url = maybe_create_github_pr(run, request, pr_body, policy)
        if pr_url:
            run.outputs["pr_url"] = pr_url
        run.status = RunStatus.COMPLETED
        store.save_run(run)
        return run
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.last_error = f"Fail-safe stop: {exc}"
        store.write_artifact(
            run.id,
            "fail-safe.json",
            {"error": str(exc), "action": "manual_intervention_required"},
        )
        store.save_run(run)
        return run


def maybe_create_github_pr(run: Run, request: RunRequest, pr_body: str, policy: RuntimePolicy) -> str:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    repo_slug = request.repo_slug.strip()
    if not token or "/" not in repo_slug:
        return ""
    owner, repo = repo_slug.split("/", 1)
    client = GitHubClient(GitHubConfig(token=token, owner=owner, repo=repo))
    title = f"auto: {run.outputs.get('summary', run.input_text[:70])}"
    return client.create_pull_request(
        title=title,
        body=pr_body,
        head=run.branch_name,
        base=policy.base_branch,
        draft=policy.draft_pr,
    )


def run_hardening_report(state_dir: Path) -> dict[str, Any]:
    store = JSONStateStore(base_dir=state_dir)
    runs = store.list_runs()
    total = len(runs)
    completed = len([r for r in runs if r.status == RunStatus.COMPLETED])
    failed = len([r for r in runs if r.status == RunStatus.FAILED])
    needs_input = len([r for r in runs if r.status == RunStatus.NEEDS_INPUT])
    retries = sum(sum(task.attempts for task in run.tasks) for run in runs)
    metrics = {
        "total_runs": total,
        "completed_runs": completed,
        "failed_runs": failed,
        "needs_input_runs": needs_input,
        "pass_rate": round((completed / total) * 100, 2) if total else 0.0,
        "avg_attempts_per_run": round(retries / total, 2) if total else 0.0,
    }
    (state_dir / "hardening-metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-agent GitOps orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)

    manual = sub.add_parser("run", help="Run full cycle from manual text")
    manual.add_argument("--text", required=True, help="User request text")
    manual.add_argument("--repo-path", required=True, help="Local repository path")
    manual.add_argument("--repo-slug", default="", help="GitHub repo slug owner/name")

    event = sub.add_parser("github-event", help="Run from GitHub webhook payload")
    event.add_argument("--event-type", required=True, help="Webhook event type")
    event.add_argument("--payload-file", required=True, help="Path to event JSON payload")
    event.add_argument("--repo-path", required=True, help="Local repository path")

    report = sub.add_parser("hardening-report", help="Generate run quality metrics")
    report.add_argument("--state-dir", default="state", help="State directory path")

    parser.add_argument("--state-dir", default="state", help="State directory path")
    parser.add_argument("--max-retries", type=int, default=3, help="Retry limit per task")
    parser.add_argument("--max-cycles", type=int, default=20, help="Max orchestration cycles")
    parser.add_argument("--branch-prefix", default="auto", help="Branch prefix")
    parser.add_argument("--base-branch", default="main", help="Base branch for branches and PR")
    parser.add_argument("--dry-run", action="store_true", help="Skip commit/push/PR")
    parser.add_argument("--local-only", action="store_true", help="Run full local cycle without push/PR")
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()
    if args.command == "hardening-report":
        metrics = run_hardening_report(Path(args.state_dir))
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        return

    policy = RuntimePolicy(
        max_retries=args.max_retries,
        max_cycles=args.max_cycles,
        branch_prefix=args.branch_prefix,
        base_branch=args.base_branch,
        local_only=args.local_only,
    )
    if args.command == "run":
        trigger = ManualTrigger(repo_path=args.repo_path, repo_slug=args.repo_slug)
        request = trigger.to_request(args.text)
    else:
        trigger = GitHubEventTrigger(repo_path=args.repo_path)
        request = trigger.from_file(args.event_type, args.payload_file)

    result = run_request(
        request,
        policy,
        state_dir=Path(args.state_dir),
        dry_run=args.dry_run,
    )
    print(
        json.dumps(
            {
                "run_id": result.id,
                "status": result.status.value,
                "branch_name": result.branch_name,
                "error": result.last_error,
                "pr_url": result.outputs.get("pr_url", ""),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
