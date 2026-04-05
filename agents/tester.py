"""Tester agent: generates or updates tests for code changes.

In agentic mode (Claude Code), the tester directly creates test files
in the repository and can even run them to verify they pass.
"""

from __future__ import annotations

import json
import re

from core.config import get_settings
from core.models import AgentRole, LLMMessage
from agents.base import BaseAgent

SYSTEM_PROMPT = """\
You are a senior QA engineer and test developer. Given code changes and the project \
context, generate appropriate tests.

Your output MUST be a valid JSON object:
{
  "test_files": [
    {
      "path": "tests/test_something.py",
      "content": "full test file content",
      "description": "what these tests cover"
    }
  ],
  "test_command": "the command to run tests (e.g. pytest tests/)",
  "coverage_notes": "what is and isn't covered"
}

Rules:
- Use the project's existing test framework if detectable, otherwise use pytest.
- Write meaningful tests, not just stubs.
- Output ONLY the JSON.
"""

AGENTIC_SYSTEM = """\
You are a senior QA engineer. Write tests for recent code changes in this repository. \
Use the project's existing test framework and conventions. Write meaningful tests. \
Do NOT attempt to run tests — only read the source code and write test files.\
"""

AGENTIC_PROMPT_TEMPLATE = """\
Write tests for the code changes in this repository.

## Git diff of the changes
```diff
{diff}
```

## Instructions

1. Read the changed files to understand what was modified
2. Look at existing tests (if any) to understand the testing patterns used
3. Create or update test files for the changed code
4. Summarize what tests you wrote and what they cover

Focus on:
- Unit tests for new/modified functions
- Edge cases
- Error handling paths

IMPORTANT: Do NOT run tests or any shell commands. Only read source files and write test files.
If the diff only contains configuration/YAML/Markdown changes with no testable logic,
briefly explain that and create a minimal smoke test if appropriate, then finish.
"""


class TesterAgent(BaseAgent):
    role = AgentRole.TESTER

    def _build_messages(self, **kwargs) -> list[LLMMessage]:
        context: str = kwargs.get("context", "")
        changes: list[dict] = kwargs.get("changes", [])
        diff: str = kwargs.get("diff", "")

        if diff:
            changes_text = f"# Git diff\n```diff\n{diff}\n```"
        else:
            changes_text = ""
            for ch in changes:
                changes_text += f"\n### {ch.get('path', '?')} ({ch.get('action', '?')})\n"
                if ch.get("content"):
                    changes_text += f"```\n{ch['content']}\n```\n"

        return [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=(
                    f"# Code changes\n{changes_text}\n\n"
                    f"# Project context\n\n{context}"
                ),
            ),
        ]

    def _build_agentic_prompt(self, **kwargs) -> str:
        diff: str = kwargs.get("diff", "")
        return AGENTIC_PROMPT_TEMPLATE.format(
            diff=diff or "(inspect the repo to find recent changes)",
        )

    def _system_prompt(self, **kwargs) -> str | None:
        return AGENTIC_SYSTEM

    def _agentic_tools(self) -> list[str]:
        # No Bash — tester must not attempt to execute tests in the container.
        # The autoproger environment does not have project-specific dependencies.
        return ["Read", "Write", "Edit", "MultiEdit", "Glob", "Grep", "LS"]

    def _agentic_max_turns(self) -> int:
        s = get_settings()
        t = s.claude_code_max_turns_tester
        return t if t > 0 else s.claude_code_max_turns

    def _agentic_max_budget(self) -> float:
        return get_settings().claude_code_budget_tester

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
