"""Planner agent: analyzes an issue and the codebase to produce an implementation plan.

In agentic mode (Claude Code), the planner can directly browse the repository
to understand the codebase structure, dependencies, and relevant code before planning.
"""

from __future__ import annotations

import json
import re

from core.models import AgentRole, LLMMessage
from agents.base import BaseAgent

SYSTEM_PROMPT = """\
You are a senior software architect. Analyze the repository and the issue description \
to produce a detailed implementation plan.

You MUST output a valid JSON object with this schema:
{
  "summary": "Brief description of what needs to be done",
  "steps": [
    {
      "description": "What this step does",
      "files": ["list of file paths to create or modify"],
      "action": "create | modify | delete"
    }
  ],
  "dependencies": ["any new packages/dependencies needed"],
  "risks": ["potential issues or edge cases"],
  "estimated_complexity": "low | medium | high"
}

IMPORTANT: Your final message MUST contain ONLY the JSON object, nothing else.\
"""

AGENTIC_PROMPT_TEMPLATE = """\
Analyze this repository and plan the implementation for the following issue.

## Issue: {issue_title}

{issue_body}

## Instructions

1. Browse the repository structure to understand the project layout
2. Read key files relevant to the issue
3. Identify what needs to change
4. Produce a structured implementation plan

Your final response MUST be a JSON object with this schema:
{{
  "summary": "Brief description of what needs to be done",
  "steps": [
    {{
      "description": "What this step does",
      "files": ["list of file paths to create or modify"],
      "action": "create | modify | delete"
    }}
  ],
  "dependencies": ["any new packages/dependencies needed"],
  "risks": ["potential issues or edge cases"],
  "estimated_complexity": "low | medium | high"
}}
"""


class PlannerAgent(BaseAgent):
    role = AgentRole.PLANNER

    def _build_messages(self, **kwargs) -> list[LLMMessage]:
        context: str = kwargs.get("context", "")
        issue_title: str = kwargs["issue_title"]
        issue_body: str = kwargs["issue_body"]

        return [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=(
                    f"# Issue: {issue_title}\n\n{issue_body}\n\n"
                    f"# Project context\n\n{context}"
                ),
            ),
        ]

    def _build_agentic_prompt(self, **kwargs) -> str:
        return AGENTIC_PROMPT_TEMPLATE.format(
            issue_title=kwargs["issue_title"],
            issue_body=kwargs["issue_body"],
        )

    def _system_prompt(self, **kwargs) -> str | None:
        return (
            "You are a senior software architect. Analyze the repository thoroughly "
            "before producing your plan. Use Read, Glob, Grep, and LS to understand "
            "the codebase. Your final output must be a valid JSON plan."
        )

    def _agentic_tools(self) -> list[str]:
        return ["Read", "Glob", "Grep", "LS", "Bash"]

    def _agentic_max_turns(self) -> int:
        return 20

    def _parse_response(self, content: str) -> dict:
        return _extract_json(content)

    def _parse_agentic_result(self, result) -> dict:
        parsed = _extract_json(result.content)
        parsed["num_turns"] = result.num_turns
        parsed["cost_usd"] = result.cost_usd
        return parsed


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw": text}
