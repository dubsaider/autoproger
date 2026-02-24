"""Developer agent: prepares implementation intents for git execution."""

from __future__ import annotations

from agents.base import AgentResult, BaseAgent


class DeveloperAgent(BaseAgent):
    role_name = "developer"

    def run(self, payload: dict) -> AgentResult:
        task_title = payload.get("task_title", "Implementation task")
        changes = [
            "Implement changes according to analyst spec",
            "Keep modifications limited to impacted modules",
            "Document rationale for non-obvious decisions",
        ]
        return AgentResult(
            success=True,
            summary=f"Developer plan prepared: {task_title}",
            artifacts={"developer_plan": changes},
        )
