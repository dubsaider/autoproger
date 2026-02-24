"""Main orchestration loop with retries and escalation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from agents import AnalystAgent, DevOpsAgent, DeveloperAgent, QAAgent, TesterAgent
from agents.base import AgentResult, BaseAgent
from orchestrator.router import AgentRouter
from state.models import AgentExecution, Run, RunRequest, RunStatus, Task, TaskStatus, utc_now
from state.store import JSONStateStore


EscalationHandler = Callable[[Run, Task], None]


@dataclass(slots=True)
class OrchestratorConfig:
    retry_limit: int = 3
    dry_run: bool = False


class Orchestrator:
    """Coordinates full-cycle execution from request to QA verdict."""

    def __init__(
        self,
        state_store: JSONStateStore,
        router: AgentRouter | None = None,
        config: OrchestratorConfig | None = None,
        escalation_handler: EscalationHandler | None = None,
    ) -> None:
        self.store = state_store
        self.router = router or AgentRouter()
        self.config = config or OrchestratorConfig()
        self.escalation_handler = escalation_handler or self._default_escalation
        self.agents: dict[str, BaseAgent] = {
            "analyst": AnalystAgent(),
            "developer": DeveloperAgent(),
            "tester": TesterAgent(),
            "devops": DevOpsAgent(),
            "qa": QAAgent(),
        }

    def start_run(self, request: RunRequest, branch_name: str) -> Run:
        run = Run.create(request, branch_name=branch_name, retry_limit=self.config.retry_limit)
        intake = self.router.build_intake(request)
        run.outputs["request_type"] = intake.request_type
        run.outputs["summary"] = intake.summary
        run.tasks = intake.tasks
        run.status = RunStatus.RUNNING
        self.store.create_run(run)
        self.store.write_artifact(run.id, "intake.json", {
            "request_type": intake.request_type,
            "summary": intake.summary,
            "tasks": [t.title for t in intake.tasks],
        })
        return run

    def run_once(self, run: Run) -> Run:
        for task in run.tasks:
            if task.status == TaskStatus.DONE:
                continue
            if not self._deps_done(run.tasks, task.dependencies):
                task.status = TaskStatus.BLOCKED
                continue
            ok = self._execute_task(run, task)
            if not ok:
                if task.attempts >= run.retry_limit:
                    run.status = RunStatus.NEEDS_INPUT
                    run.last_error = f"Task {task.id} failed after {task.attempts} attempts"
                    self.escalation_handler(run, task)
                    self.store.save_run(run)
                    return run
                task.status = TaskStatus.QUEUED
                self.store.save_run(run)
                return run
        if all(task.status == TaskStatus.DONE for task in run.tasks):
            run.status = RunStatus.COMPLETED
        elif any(task.status == TaskStatus.FAILED for task in run.tasks):
            run.status = RunStatus.FAILED
        else:
            run.status = RunStatus.RUNNING
        self.store.save_run(run)
        return run

    def run_until_terminal(self, run: Run, max_cycles: int = 20) -> Run:
        cycles = 0
        while cycles < max_cycles and run.status in {RunStatus.RUNNING, RunStatus.PENDING}:
            cycles += 1
            run = self.run_once(run)
            if self.config.dry_run:
                break
        if cycles >= max_cycles and run.status not in {RunStatus.COMPLETED, RunStatus.NEEDS_INPUT, RunStatus.FAILED}:
            run.status = RunStatus.NEEDS_INPUT
            run.last_error = "Max orchestration cycles reached"
            self.store.save_run(run)
        return run

    def _execute_task(self, run: Run, task: Task) -> bool:
        agent = self.agents.get(task.owner)
        if not agent:
            task.status = TaskStatus.FAILED
            task.last_error = f"Unknown agent: {task.owner}"
            return False
        task.status = TaskStatus.IN_PROGRESS
        task.attempts += 1
        execution = AgentExecution(
            id=str(uuid4()),
            run_id=run.id,
            agent=task.owner,
            task_id=task.id,
            status="running",
            started_at=utc_now(),
        )
        run.executions.append(execution)
        payload = {
            "run_id": run.id,
            "task_id": task.id,
            "task_title": task.title,
            "input_text": run.input_text,
            "acceptance_criteria": task.acceptance_criteria,
            "outputs": run.outputs,
        }
        result = agent.run(payload)
        return self._finalize_execution(run, task, execution, result)

    def _finalize_execution(
        self,
        run: Run,
        task: Task,
        execution: AgentExecution,
        result: AgentResult,
    ) -> bool:
        execution.finished_at = utc_now()
        execution.summary = result.summary
        execution.warnings = result.warnings
        execution.artifacts = result.artifacts
        execution.status = "success" if result.success else "failed"
        artifact_name = f"{execution.agent}-{execution.task_id}.json"
        self.store.write_artifact(run.id, artifact_name, {
            "summary": result.summary,
            "warnings": result.warnings,
            "artifacts": result.artifacts,
        })
        key = f"{execution.agent}_{task.id}"
        run.outputs[key] = result.artifacts
        if result.success:
            task.status = TaskStatus.DONE
            task.last_error = ""
            self.store.save_run(run)
            return True
        task.status = TaskStatus.FAILED
        task.last_error = result.summary
        self.store.save_run(run)
        return False

    @staticmethod
    def _deps_done(tasks: list[Task], dependency_ids: list[str]) -> bool:
        index = {t.id: t for t in tasks}
        return all(index.get(dep_id) and index[dep_id].status == TaskStatus.DONE for dep_id in dependency_ids)

    def _default_escalation(self, run: Run, task: Task) -> None:
        self.store.write_artifact(
            run.id,
            "escalation.json",
            {
                "run_id": run.id,
                "task_id": task.id,
                "reason": run.last_error,
                "action": "manual_review_required",
            },
        )
