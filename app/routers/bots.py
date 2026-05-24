import logging
import os
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import CurrentUser, DbSession
from app.models import Agency
from app.schemas.bots import (
    BotActionResponse,
    BotStartRequest,
    BotStatusResponse,
    BotTokenResponse,
)
from bot import manager as bot_manager

router = APIRouter(prefix="/bots", tags=["bots"])
logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def _mask_token(token: str) -> str:
    token = token.strip()
    if len(token) <= 8:
        return f"...{token}"
    return f"...{token[-8:]}"


async def _get_agency(db: DbSession, agency_id: uuid.UUID) -> Agency:
    result = await db.execute(select(Agency).where(Agency.id == agency_id))
    agency = result.scalar_one_or_none()
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )
    return agency


@router.get("/token", response_model=BotTokenResponse)
async def get_agency_bot_token(
    db: DbSession,
    current_user: CurrentUser,
) -> BotTokenResponse:
    agency = await _get_agency(db, current_user.agency_id)
    if not agency.telegram_bot_token:
        return BotTokenResponse(has_token=False)
    return BotTokenResponse(
        has_token=True,
        masked=_mask_token(agency.telegram_bot_token),
    )


@router.post("/start", response_model=BotActionResponse)
async def start_agency_bot(
    body: BotStartRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> BotActionResponse:
    agency = await _get_agency(db, current_user.agency_id)

    token = body.token.strip() if body.token else None
    if not token:
        token = agency.telegram_bot_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Токен не указан",
        )

    agency.telegram_bot_token = token

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This bot token is already used by another agency",
        ) from None

    agency_id = str(current_user.agency_id)
    await bot_manager.stop_bot(agency_id)
    await bot_manager.start_bot(agency_id, token, BACKEND_URL)

    return BotActionResponse(status="started")


@router.post("/stop", response_model=BotActionResponse)
async def stop_agency_bot(
    db: DbSession,
    current_user: CurrentUser,
) -> BotActionResponse:
    await _get_agency(db, current_user.agency_id)
    agency_id = str(current_user.agency_id)
    await bot_manager.stop_bot(agency_id)
    return BotActionResponse(status="stopped")


@router.get("/status", response_model=BotStatusResponse)
async def get_agency_bot_status(
    db: DbSession,
    current_user: CurrentUser,
) -> BotStatusResponse:
    agency = await _get_agency(db, current_user.agency_id)
    agency_id = str(current_user.agency_id)
    is_running = agency_id in bot_manager.running_bots
    bot_username: str | None = None
    if is_running:
        application = bot_manager.running_bots[agency_id]
        try:
            me = await application.bot.get_me()
            bot_username = me.username
        except Exception:
            logger.exception("Failed to fetch bot username for agency %s", agency_id)

    return BotStatusResponse(
        status="running" if is_running else "stopped",
        has_token=bool(agency.telegram_bot_token),
        bot_username=bot_username,
    )
