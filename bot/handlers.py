"""Telegram bot command handlers."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from core.task_manager import TaskManager
from storage.database import async_session
from storage import repositories as db

log = logging.getLogger(__name__)
task_manager = TaskManager()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 Autoproger v2 Bot\n\n"
        "Commands:\n"
        "/status — system status\n"
        "/tasks — list pending tasks\n"
        "/approve <task_id> — approve a task\n"
        "/repos — list repos\n"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session() as session:
        repos = await db.list_repos(session)
        tasks = await db.list_tasks(session)
    pending = sum(1 for t in tasks if t.status == "pending")
    in_prog = sum(1 for t in tasks if t.status == "in_progress")
    done = sum(1 for t in tasks if t.status == "completed")
    await update.message.reply_text(
        f"📊 Status\n"
        f"Repos: {len(repos)}\n"
        f"Tasks: {len(tasks)} (pending={pending}, running={in_prog}, done={done})"
    )


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session() as session:
        tasks = await db.list_tasks(session, status="pending")
    if not tasks:
        await update.message.reply_text("No pending tasks.")
        return
    lines = ["📋 Pending tasks:\n"]
    for t in tasks[:15]:
        lines.append(f"`{t.id}` — #{t.issue_number} {t.issue_title}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /approve <task_id>")
        return
    task_id = args[0]
    try:
        await task_manager.approve_task(task_id)
        await update.message.reply_text(f"✅ Task `{task_id}` approved!", parse_mode="Markdown")
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_repos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session() as session:
        repos = await db.list_repos(session)
    if not repos:
        await update.message.reply_text("No repositories configured.")
        return
    lines = ["📦 Repositories:\n"]
    for r in repos:
        lines.append(f"• `{r.id}` — {r.platform} {r.url} [{r.autonomy}]")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
