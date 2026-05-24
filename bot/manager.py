import logging

from telegram.ext import Application

logger = logging.getLogger(__name__)

# Хранилище запущенных ботов: {agency_id: Application}
running_bots: dict[str, Application] = {}


async def start_bot(agency_id: str, token: str, backend_url: str) -> None:
    if agency_id in running_bots:
        logger.info("Bot for agency %s already running", agency_id)
        return

    app = Application.builder().token(token).build()

    from bot.handlers import build_conversation_handler

    app.add_handler(build_conversation_handler(agency_id, backend_url))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    running_bots[agency_id] = app
    logger.info("Bot started for agency %s", agency_id)


async def stop_bot(agency_id: str) -> None:
    if agency_id not in running_bots:
        return
    app = running_bots.pop(agency_id)
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    logger.info("Bot stopped for agency %s", agency_id)


async def restart_bot(agency_id: str, token: str, backend_url: str) -> None:
    await stop_bot(agency_id)
    await start_bot(agency_id, token, backend_url)


async def send_message(agency_id: str, telegram_id: str, text: str) -> None:
    if agency_id not in running_bots:
        raise RuntimeError("Bot not running")
    application = running_bots[agency_id]
    await application.bot.send_message(chat_id=int(telegram_id), text=text)


async def send_rejection(agency_id: str, telegram_id: str, candidate_name: str) -> None:
    text = (
        f"Здравствуйте, {candidate_name}!\n"
        "К сожалению, после рассмотрения вашей кандидатуры "
        "мы приняли решение продолжить поиск с другими кандидатами.\n"
        "Это не значит, что вы плохой специалист — "
        "просто в этот раз не совпали требования.\n"
        "Желаем успехов в поиске! 🙏"
    )
    await send_message(agency_id, telegram_id, text)
