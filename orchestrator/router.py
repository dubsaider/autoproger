"""Task decomposition and routing policy for role agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import uuid4

from state.models import RunRequest, Task, TaskStatus


@dataclass(slots=True)
class IntakeResult:
    request_type: str
    summary: str
    tasks: list[Task]


class AgentRouter:
    """Turns free-form input into executable role tasks."""

    def classify(self, text: str) -> str:
        normalized = text.lower()
        feature_tokens = ("feature", "добав", "реализ", "new", "улучш")
        bug_tokens = ("bug", "fix", "ошиб", "слом", "пад")
        infra_tokens = ("deploy", "ci", "cd", "docker", "k8s", "infra", "pipeline")
        if any(token in normalized for token in infra_tokens):
            return "infra"
        if any(token in normalized for token in bug_tokens):
            return "bugfix"
        if any(token in normalized for token in feature_tokens):
            return "feature"
        return "ambiguous"

    def build_intake(self, request: RunRequest) -> IntakeResult:
        request_type = self.classify(request.text)
        tasks = self._tasks_for_type(request_type)
        summary = request.text.strip().splitlines()[0][:180] if request.text.strip() else "Empty request"
        return IntakeResult(request_type=request_type, summary=summary, tasks=tasks)

    def _tasks_for_type(self, request_type: str) -> list[Task]:
        if request_type == "feature":
            roles = ["analyst", "developer", "tester", "devops", "qa"]
        elif request_type == "bugfix":
            roles = ["analyst", "developer", "tester", "qa"]
        elif request_type == "infra":
            roles = ["devops", "tester", "qa"]
        else:
            roles = ["analyst", "developer", "tester", "devops", "qa"]

        tasks: list[Task] = []
        dependency_chain: list[str] = []
        for role in roles:
            task_id = str(uuid4())
            tasks.append(
                Task(
                    id=task_id,
                    title=self._task_title(role, request_type),
                    owner=role,
                    acceptance_criteria=self._acceptance_for_role(role),
                    dependencies=list(dependency_chain),
                    status=TaskStatus.QUEUED,
                )
            )
            dependency_chain = [task_id]
        return tasks

    @staticmethod
    def _task_title(role: str, request_type: str) -> str:
        return f"{role.capitalize()} step for {request_type}"

    @staticmethod
    def _acceptance_for_role(role: str) -> list[str]:
        criteria: dict[str, Iterable[str]] = {
            "analyst": (
                "Requirements are explicit and testable",
                "Scope and out-of-scope are documented",
                "Task breakdown is ready for execution",
            ),
            "developer": (
                "Code changes map to task requirements",
                "Implementation notes and touched files are documented",
            ),
            "tester": (
                "Automated checks or rationale for skips provided",
                "Regression risks are listed",
            ),
            "devops": (
                "Build/deploy impacts are checked",
                "Rollback note is prepared if needed",
            ),
            "qa": (
                "Acceptance criteria are validated",
                "Final release verdict is explicit",
            ),
        }
        return list(criteria.get(role, ("Task output provided",)))
