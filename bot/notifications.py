"""Telegram notification helpers."""

from __future__ import annotations

import logging

from telegram import Bot

from core.config import get_settings

log = logging.getLogger(__name__)


async def _get_bot() -> Bot | None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        return None
    return Bot(token=settings.telegram_bot_token)


async def _admin_chat_id() -> str | None:
    return get_settings().telegram_admin_chat_id or None


async def notify_new_task(task_id: str, issue_title: str, issue_number: int, repo_url: str) -> None:
    bot = await _get_bot()
    chat_id = await _admin_chat_id()
    if not bot or not chat_id:
        return
    text = (
        f"📋 *New task* `{task_id}`\n"
        f"Issue #{issue_number}: {_escape(issue_title)}\n"
        f"Repo: {_escape(repo_url)}\n\n"
        f"Use /approve {task_id} to approve"
    )
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception:
        log.exception("Failed to send Telegram notification")


async def notify_plan_ready(task_id: str, summary: str) -> None:
    bot = await _get_bot()
    chat_id = await _admin_chat_id()
    if not bot or not chat_id:
        return
    text = (
        f"📝 *Plan ready* for task `{task_id}`\n\n"
        f"{_escape(summary[:500])}\n\n"
        f"Use /approve {task_id} to proceed"
    )
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception:
        log.exception("Failed to send Telegram notification")


async def notify_pr_created(task_id: str, pr_url: str) -> None:
    bot = await _get_bot()
    chat_id = await _admin_chat_id()
    if not bot or not chat_id:
        return
    text = (
        f"✅ *PR created* for task `{task_id}`\n"
        f"[View PR]({pr_url})"
    )
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception:
        log.exception("Failed to send Telegram notification")


async def notify_error(task_id: str, error: str) -> None:
    bot = await _get_bot()
    chat_id = await _admin_chat_id()
    if not bot or not chat_id:
        return
    text = f"❌ *Task failed* `{task_id}`\n{_escape(error[:300])}"
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception:
        log.exception("Failed to send Telegram notification")


def _escape(text: str) -> str:
    for ch in ("_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        text = text.replace(ch, f"\\{ch}")
    return text
