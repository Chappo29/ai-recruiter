"""Telegram bot polling — single-process only (bot-worker)."""

import logging

from telegram.ext import Application

logger = logging.getLogger(__name__)

# Lives only in the bot-worker process.
running_bots: dict[str, Application] = {}


async def start_polling(agency_id: str, token: str, backend_url: str) -> None:
    if agency_id in running_bots:
        logger.info("Bot polling already active for agency %s", agency_id)
        return

    from app.core.config import BOT_RATE_LIMIT_SEC

    app = Application.builder().token(token).build()

    from telegram import Update
    from telegram.ext import TypeHandler

    from bot.handlers import build_conversation_handler
    from bot.middleware import ThrottleHandler

    # Group -2: rate limit runs first (can block update entirely).
    # Group -1: session restore — must be in its own group, otherwise (as a
    # TypeHandler matching every Update) it consumes the update inside the
    # group and the conv_handler never sees /start or any other message.
    # Group  0: actual conversation handler.
    app.add_handler(ThrottleHandler(rate_limit=BOT_RATE_LIMIT_SEC), group=-2)

    conv_handler, restore_handler = build_conversation_handler(agency_id, backend_url)
    app.add_handler(TypeHandler(Update, restore_handler), group=-1)
    app.add_handler(conv_handler, group=0)

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    running_bots[agency_id] = app
    logger.info("Bot polling started for agency %s", agency_id)


async def stop_polling(agency_id: str) -> None:
    if agency_id not in running_bots:
        return
    app = running_bots.pop(agency_id)
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    logger.info("Bot polling stopped for agency %s", agency_id)


async def restart_polling(agency_id: str, token: str, backend_url: str) -> None:
    await stop_polling(agency_id)
    await start_polling(agency_id, token, backend_url)


def is_polling(agency_id: str) -> bool:
    return agency_id in running_bots


async def get_bot_username(agency_id: str) -> str | None:
    app = running_bots.get(agency_id)
    if app is None:
        return None
    try:
        me = await app.bot.get_me()
        return me.username
    except Exception:
        logger.exception("get_me failed for agency %s", agency_id)
        return None
