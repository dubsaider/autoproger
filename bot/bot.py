"""Telegram bot setup and run."""

from __future__ import annotations

import logging

from telegram.ext import ApplicationBuilder, CommandHandler

from bot.handlers import cmd_approve, cmd_repos, cmd_start, cmd_status, cmd_tasks
from core.config import get_settings

log = logging.getLogger(__name__)


def create_bot_app():
    settings = get_settings()
    if not settings.telegram_bot_token:
        log.warning("TELEGRAM_BOT_TOKEN not set — bot disabled")
        return None

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("repos", cmd_repos))
    return app


async def run_bot() -> None:
    """Start the bot in polling mode (blocking)."""
    app = create_bot_app()
    if app is None:
        return
    log.info("Telegram bot starting...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    log.info("Telegram bot is running")
