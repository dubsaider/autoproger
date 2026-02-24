"""JSON-based persistence for orchestration state and artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Run, run_from_dict, utc_now


class JSONStateStore:
    """Persists each run as JSON and keeps lightweight index files."""

    def __init__(self, base_dir: Path | str = "state") -> None:
        self.base_dir = Path(base_dir)
        self.runs_dir = self.base_dir / "runs"
        self.artifacts_dir = Path("artifacts")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def _run_file(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.json"

    def create_run(self, run: Run) -> Run:
        run.status = run.status
        run.updated_at = utc_now()
        self.save_run(run)
        self.ensure_artifacts_dir(run.id)
        return run

    def save_run(self, run: Run) -> None:
        run.updated_at = utc_now()
        payload = run.as_dict()
        self._run_file(run.id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_run(self, run_id: str) -> Run | None:
        path = self._run_file(run_id)
        if not path.exists():
            return None
        return run_from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_runs(self) -> list[Run]:
        runs: list[Run] = []
        for run_file in sorted(self.runs_dir.glob("*.json")):
            payload = json.loads(run_file.read_text(encoding="utf-8"))
            runs.append(run_from_dict(payload))
        return runs

    def ensure_artifacts_dir(self, run_id: str) -> Path:
        run_dir = self.artifacts_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def write_artifact(
        self,
        run_id: str,
        name: str,
        content: str | dict[str, Any] | list[Any],
    ) -> Path:
        run_dir = self.ensure_artifacts_dir(run_id)
        path = run_dir / name
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
