"""Developer agent: implements code changes based on a plan.

In agentic mode (Claude Code), the developer directly edits files in the repository —
no need to generate JSON with file contents. Claude Code uses its native tools
(Write, Edit, MultiEdit) to make changes, and we detect what changed via git diff.
"""

from __future__ import annotations

import json
import re

from core.config import get_settings
from core.models import AgentRole, LLMMessage
from agents.base import BaseAgent

SYSTEM_PROMPT = """\
You are an expert software developer. Given an implementation plan and the current \
source code, generate the exact file changes needed.

Your output MUST be a valid JSON object:
{
  "changes": [
    {
      "path": "relative/path/to/file.py",
      "action": "create | modify | delete",
      "content": "full file content for create/modify, null for delete",
      "explanation": "brief reason for this change"
    }
  ],
  "commit_message": "A clear, conventional commit message"
}

Rules:
- For "modify", provide the COMPLETE new file content (not a diff).
- Keep changes minimal and focused on the plan.
- Follow the existing code style.
- Output ONLY the JSON, no extra text.
"""

AGENTIC_SYSTEM = """\
You are an expert software developer working directly on a codebase. \
Implement the requested changes by editing files in-place. \
Follow existing code style and conventions. Keep changes minimal and focused.\
"""

AGENTIC_PROMPT_TEMPLATE = """\
Implement the following plan in this repository.

## Plan
```json
{plan_json}
```

{review_feedback}

## Instructions

1. Read the relevant files first to understand the current code
2. Make the necessary changes using Edit/Write tools
3. After making changes, verify them by reading the modified files
4. Make sure all imports are correct and the code is consistent

Do NOT create unnecessary files. Follow existing patterns and code style.
When done, summarize what you changed as your final message.
"""


class DeveloperAgent(BaseAgent):
    role = AgentRole.DEVELOPER

    def _build_messages(self, **kwargs) -> list[LLMMessage]:
        context: str = kwargs.get("context", "")
        plan: dict = kwargs["plan"]

        return [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=(
                    f"# Implementation plan\n\n```json\n{json.dumps(plan, indent=2)}\n```\n\n"
                    f"# Project context\n\n{context}"
                ),
            ),
        ]

    def _build_agentic_prompt(self, **kwargs) -> str:
        plan: dict = kwargs["plan"]
        feedback = ""
        if "review_feedback" in plan:
            issues = plan["review_feedback"]
            feedback = "\n## Review feedback to address\n"
            for issue in issues:
                feedback += f"- [{issue.get('severity', '?')}] {issue.get('file', '?')}: {issue.get('description', '')}\n"
                if issue.get("fix_suggestion"):
                    feedback += f"  Suggestion: {issue['fix_suggestion']}\n"

        return AGENTIC_PROMPT_TEMPLATE.format(
            plan_json=json.dumps(plan, indent=2, default=str),
            review_feedback=feedback,
        )

    def _system_prompt(self, **kwargs) -> str | None:
        return AGENTIC_SYSTEM

    def _agentic_tools(self) -> list[str]:
        return ["Read", "Write", "Edit", "MultiEdit", "Glob", "Grep", "LS", "Bash"]

    def _agentic_max_turns(self) -> int:
        s = get_settings()
        t = s.claude_code_max_turns_developer
        return t if t > 0 else s.claude_code_max_turns

    def _agentic_max_budget(self) -> float:
        return get_settings().claude_code_budget_developer

    def _parse_response(self, content: str) -> dict:
        return _extract_json(content)

    def _parse_agentic_result(self, result) -> dict:
        return {
            "summary": result.content,
            "num_turns": result.num_turns,
            "cost_usd": result.cost_usd,
            "agentic": True,
        }


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw": text}
