"""Tester agent: defines verification plan for quality gates."""

from __future__ import annotations

from agents.base import AgentResult, BaseAgent


class TesterAgent(BaseAgent):
    role_name = "tester"

    def run(self, payload: dict) -> AgentResult:
        checks = payload.get("checks") or ["lint", "unit", "build", "smoke"]
        return AgentResult(
            success=True,
            summary="Test strategy prepared",
            artifacts={
                "test_plan": {
                    "checks": checks,
                    "regression_focus": payload.get("regression_focus", "Core user flows"),
                }
            },
        )
