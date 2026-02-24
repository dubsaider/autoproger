"""Developer agent: prepares implementation intents for git execution."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agents.base import AgentResult, BaseAgent


class DeveloperAgent(BaseAgent):
    role_name = "developer"

    def run(self, payload: dict) -> AgentResult:
        task_title = payload.get("task_title", "Implementation task")
        repo_path = Path(str(payload.get("repo_path", ".")))
        run_id = str(payload.get("run_id", "unknown-run"))
        request_text = str(payload.get("input_text", "")).strip()
        journal_path = repo_path / "AUTO_IMPROVEMENTS.md"
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        entry_lines = [
            "",
            f"## Run {run_id}",
            f"- Task: {task_title}",
            f"- Timestamp (UTC): {timestamp}",
            f"- Request: {request_text or 'N/A'}",
            "- Action: automated developer stage executed and repository journal updated.",
        ]
        try:
            if journal_path.exists():
                current = journal_path.read_text(encoding="utf-8")
            else:
                current = "# Auto Improvements Journal\n"
            journal_path.write_text(current.rstrip() + "\n" + "\n".join(entry_lines) + "\n", encoding="utf-8")
        except Exception as exc:
            return AgentResult(
                success=False,
                summary=f"Developer stage failed to write repository journal: {exc}",
                artifacts={"changed_files": []},
            )
        return AgentResult(
            success=True,
            summary=f"Developer changes applied: {task_title}",
            artifacts={"changed_files": [str(journal_path.name)]},
        )
