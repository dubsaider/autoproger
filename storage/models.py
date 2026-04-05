"""SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from storage.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class RepoORM(Base):
    __tablename__ = "repos"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=_new_id)
    platform: Mapped[str] = mapped_column(String(10))
    url: Mapped[str] = mapped_column(String(500))
    token: Mapped[str] = mapped_column(String(500))
    autonomy: Mapped[str] = mapped_column(String(20), default="semi_auto")
    watch_labels: Mapped[dict] = mapped_column(JSON, default=list)
    branch_prefix: Mapped[str] = mapped_column(String(50), default="autoproger/")
    llm_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    max_file_changes: Mapped[int] = mapped_column(Integer, default=20)
    allowed_paths: Mapped[dict] = mapped_column(JSON, default=list)
    denied_paths: Mapped[dict] = mapped_column(JSON, default=list)
    default_branch: Mapped[str] = mapped_column(String(50), default="main")
    gitlab_url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TaskORM(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=_new_id)
    repo_id: Mapped[str] = mapped_column(String(12), index=True)
    issue_number: Mapped[int] = mapped_column(Integer)
    issue_title: Mapped[str] = mapped_column(String(500))
    issue_body: Mapped[str] = mapped_column(Text, default="")
    issue_labels: Mapped[dict] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RunORM(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=_new_id)
    task_id: Mapped[str] = mapped_column(String(12), index=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    agent_results: Mapped[dict] = mapped_column(JSON, default=list)
    pr_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    branch_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
