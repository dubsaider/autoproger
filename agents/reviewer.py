"""Reviewer agent: reviews code changes for quality issues.

In agentic mode, the reviewer can browse the repo and inspect the actual diff
rather than relying on changes serialized in the prompt.
"""

from __future__ import annotations

import json
import re

from core.models import AgentRole, LLMMessage
from agents.base import BaseAgent

SYSTEM_PROMPT = """\
You are an expert code reviewer. Review the proposed code changes for bugs, \
security issues, style problems, and correctness.

Your output MUST be a valid JSON object:
{
  "approved": true | false,
  "issues": [
    {
      "severity": "critical | warning | suggestion",
      "file": "path/to/file",
      "description": "What's wrong",
      "fix_suggestion": "How to fix it"
    }
  ],
  "summary": "Overall assessment"
}

Be strict on critical issues (bugs, security), lenient on minor style preferences.
Output ONLY the JSON.
"""

AGENTIC_SYSTEM = """\
You are an expert code reviewer. Review the recent changes in this repository. \
Focus on bugs, security issues, correctness, and code quality. \
Be strict on critical issues, lenient on minor style preferences.\
"""

AGENTIC_PROMPT_TEMPLATE = """\
Review the code changes in this repository.

## Plan that was implemented
```json
{plan_json}
```

## Git diff of the changes
```diff
{diff}
```

## Instructions

1. Read the diff carefully
2. If needed, read the full files to understand context
3. Check for bugs, security issues, missing error handling, type errors, etc.
4. Your final response MUST be a JSON object:

{{
  "approved": true | false,
  "issues": [
    {{
      "severity": "critical | warning | suggestion",
      "file": "path/to/file",
      "description": "What's wrong",
      "fix_suggestion": "How to fix it"
    }}
  ],
  "summary": "Overall assessment"
}}
"""


class ReviewerAgent(BaseAgent):
    role = AgentRole.REVIEWER

    def _build_messages(self, **kwargs) -> list[LLMMessage]:
        changes: list[dict] = kwargs.get("changes", [])
        plan: dict = kwargs["plan"]
        diff: str = kwargs.get("diff", "")

        if diff:
            review_content = f"# Git diff\n```diff\n{diff}\n```"
        else:
            review_content = ""
            for ch in changes:
                review_content += f"\n### {ch.get('path', '?')} ({ch.get('action', '?')})\n"
                if ch.get("content"):
                    review_content += f"```\n{ch['content']}\n```\n"

        return [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=(
                    f"# Plan\n```json\n{json.dumps(plan, indent=2)}\n```\n\n"
                    f"# Proposed changes\n{review_content}"
                ),
            ),
        ]

    def _build_agentic_prompt(self, **kwargs) -> str:
        plan: dict = kwargs["plan"]
        diff: str = kwargs.get("diff", "")
        return AGENTIC_PROMPT_TEMPLATE.format(
            plan_json=json.dumps(plan, indent=2, default=str),
            diff=diff or "(no diff available — inspect the repo directly)",
        )

    def _system_prompt(self, **kwargs) -> str | None:
        return AGENTIC_SYSTEM

    def _agentic_tools(self) -> list[str]:
        return ["Read", "Glob", "Grep", "LS", "Bash"]

    def _agentic_max_turns(self) -> int:
        return 6

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
        return {"approved": False, "raw": text}
