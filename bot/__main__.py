"""
Bot worker entrypoint: Telegram polling + control API.

Run from project root:
    python -m bot

Environment: same as API (DATABASE_URL, INTERNAL_API_KEY, BACKEND_URL).
Control API default: http://127.0.0.1:8001
"""

import asyncio
import logging
import os

import uvicorn
from sqlalchemy import select

from app.core.config import validate_required_secrets
from app.core.load_env import load_project_env
from app.database import async_session_factory
from app.models import Agency
from app.services import bot_runtime_service
from bot import polling
from bot.worker_control import BACKEND_URL, control_app

logger = logging.getLogger(__name__)

CONTROL_HOST = os.getenv("BOT_WORKER_HOST", "127.0.0.1")
CONTROL_PORT = int(os.getenv("BOT_WORKER_PORT", "8001"))
HEARTBEAT_INTERVAL_SEC = int(os.getenv("BOT_HEARTBEAT_INTERVAL_SEC", "30"))


async def _autostart_bots() -> None:
    async with async_session_factory() as db:
        result = await db.execute(
            select(Agency).where(Agency.telegram_bot_token.isnot(None))
        )
        agencies = list(result.scalars().all())

    for agency in agencies:
        token = (agency.telegram_bot_token or "").strip()
        if not token:
            continue
        agency_id = str(agency.id)
        try:
            await polling.start_polling(agency_id, token, BACKEND_URL)
            username = await polling.get_bot_username(agency_id)
            async with async_session_factory() as db:
                await bot_runtime_service.upsert_runtime(
                    db,
                    agency.id,
                    status="running",
                    bot_username=username,
                    heartbeat=True,
                )
            logger.info("Auto-started bot for agency %s", agency_id)
        except Exception:
            logger.exception("Failed to auto-start bot for agency %s", agency_id)


async def _heartbeat_loop() -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)
        for agency_id in list(polling.running_bots.keys()):
            try:
                username = await polling.get_bot_username(agency_id)
                async with async_session_factory() as db:
                    await bot_runtime_service.upsert_runtime(
                        db,
                        agency_id,
                        status="running",
                        bot_username=username,
                        heartbeat=True,
                    )
            except Exception:
                logger.exception("Heartbeat failed for agency %s", agency_id)


async def _run_control_server() -> None:
    config = uvicorn.Config(
        control_app,
        host=CONTROL_HOST,
        port=CONTROL_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    load_project_env()
    validate_required_secrets()

    await _autostart_bots()

    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    try:
        await _run_control_server()
    finally:
        heartbeat_task.cancel()
        for agency_id in list(polling.running_bots.keys()):
            try:
                await polling.stop_polling(agency_id)
            except Exception:
                logger.exception("Failed to stop bot for agency %s", agency_id)


if __name__ == "__main__":
    asyncio.run(main())
