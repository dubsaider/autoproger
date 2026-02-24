"""QA gatekeeper agent: emits final pass/fail verdict."""

from __future__ import annotations

from agents.base import AgentResult, BaseAgent


class QAAgent(BaseAgent):
    role_name = "qa"

    def run(self, payload: dict) -> AgentResult:
        failed = payload.get("failed_gates", [])
        if failed:
            return AgentResult(
                success=False,
                summary="QA rejected release due to failed gates",
                artifacts={"qa_verdict": "fail", "failed_gates": failed},
                warnings=["Fix failed quality gates before PR promotion"],
            )
        return AgentResult(
            success=True,
            summary="QA approved release candidate",
            artifacts={"qa_verdict": "pass"},
        )
