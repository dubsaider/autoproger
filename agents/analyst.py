"""Analyst agent: transforms request into spec and backlog notes."""

from __future__ import annotations

from agents.base import AgentResult, BaseAgent


class AnalystAgent(BaseAgent):
    role_name = "analyst"

    def run(self, payload: dict) -> AgentResult:
        user_text = str(payload.get("input_text", "")).strip()
        summary = user_text.splitlines()[0][:180] if user_text else "No input provided"
        spec = {
            "summary": summary,
            "assumptions": payload.get("assumptions", []),
            "acceptance_criteria": payload.get("acceptance_criteria", []),
            "risks": [
                "Ambiguous business rules may require manual clarification",
                "Unclear non-functional constraints may impact estimates",
            ],
        }
        return AgentResult(success=True, summary="Analysis completed", artifacts={"spec": spec})
