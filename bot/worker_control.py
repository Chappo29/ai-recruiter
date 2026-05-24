"""Control-plane HTTP API for the bot-worker process."""

import logging
import os
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import get_internal_api_key
from app.database import async_session_factory
from app.models import Agency
from app.services import bot_runtime_service
from bot import polling

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

control_app = FastAPI(title="RecruitAI Bot Worker", version="0.1.0")


class StartBody(BaseModel):
    agency_id: str
    token: str
    backend_url: str | None = None


class StopBody(BaseModel):
    agency_id: str


def _check_key(x_internal_key: str) -> None:
    if x_internal_key != get_internal_api_key():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@control_app.post("/control/start")
async def control_start(
    body: StartBody,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> dict[str, str]:
    _check_key(x_internal_key)
    agency_id = body.agency_id
    backend = (body.backend_url or BACKEND_URL).rstrip("/")
    try:
        await polling.restart_polling(agency_id, body.token.strip(), backend)
        username = await polling.get_bot_username(agency_id)
        async with async_session_factory() as db:
            await bot_runtime_service.upsert_runtime(
                db,
                UUID(agency_id),
                status="running",
                bot_username=username,
                heartbeat=True,
            )
    except Exception as exc:
        logger.exception("Failed to start bot for agency %s", agency_id)
        async with async_session_factory() as db:
            await bot_runtime_service.upsert_runtime(
                db, UUID(agency_id), status="error", heartbeat=False
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return {"status": "started", "bot_username": username or ""}


@control_app.post("/control/stop")
async def control_stop(
    body: StopBody,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> dict[str, str]:
    _check_key(x_internal_key)
    await polling.stop_polling(body.agency_id)
    async with async_session_factory() as db:
        await bot_runtime_service.mark_stopped(db, UUID(body.agency_id))
    return {"status": "stopped"}


@control_app.get("/health")
async def control_health() -> dict[str, str]:
    return {"status": "ok", "polling_bots": str(len(polling.running_bots))}
