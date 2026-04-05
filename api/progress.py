"""In-memory progress event store for pipeline runs."""
from __future__ import annotations

import time
from collections import defaultdict
from typing import TypedDict


class ProgressEvent(TypedDict):
    ts: float
    level: str   # info | success | warning | error
    agent: str   # planner | developer | reviewer | tester | orchestrator
    message: str


# run_id -> list of events
_store: dict[str, list[ProgressEvent]] = defaultdict(list)


def emit(run_id: str, message: str, *, agent: str = "orchestrator", level: str = "info") -> None:
    _store[run_id].append(
        ProgressEvent(ts=time.time(), level=level, agent=agent, message=message)
    )


def get_events(run_id: str) -> list[ProgressEvent]:
    return list(_store.get(run_id, []))


def clear(run_id: str) -> None:
    _store.pop(run_id, None)
