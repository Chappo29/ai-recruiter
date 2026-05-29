"""Internal API for Telegram bot session persistence."""

import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.internal_auth import verify_internal_key
from app.core.rate_limit import internal_limit
from app.deps import DbSession
from app.services import bot_state_service

internal_router = APIRouter(prefix="/internal", tags=["internal"])


def _check_internal_key(x_internal_key: str) -> None:
    verify_internal_key(x_internal_key)


class BotStateUpsert(BaseModel):
    agency_id: str
    step: str
    user_data: dict[str, Any] = Field(default_factory=dict)


class BotStateResponse(BaseModel):
    telegram_id: str
    agency_id: str
    step: str
    user_data: dict[str, Any]


@internal_router.get("/bot-state/{telegram_id}", response_model=BotStateResponse | None)
@internal_limit()
async def get_bot_state(
    request: Request,
    telegram_id: str,
    agency_id: str,
    db: DbSession,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> BotStateResponse | None:
    _check_internal_key(x_internal_key)
    try:
        agency_uuid = uuid.UUID(agency_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid agency_id") from exc

    row = await bot_state_service.get_state(
        db, telegram_id=telegram_id, agency_id=agency_uuid
    )
    if row is None:
        return None

    return BotStateResponse(
        telegram_id=row.telegram_id,
        agency_id=str(row.agency_id),
        step=row.step,
        user_data=bot_state_service.parse_state_json(row.state_json),
    )


@internal_router.put("/bot-state/{telegram_id}", response_model=BotStateResponse)
@internal_limit()
async def upsert_bot_state(
    request: Request,
    telegram_id: str,
    body: BotStateUpsert,
    db: DbSession,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> BotStateResponse:
    _check_internal_key(x_internal_key)
    try:
        agency_uuid = uuid.UUID(body.agency_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid agency_id") from exc

    if body.step not in bot_state_service.VALID_STEPS:
        raise HTTPException(status_code=400, detail="Invalid step")

    row = await bot_state_service.save_state(
        db,
        telegram_id=telegram_id,
        agency_id=agency_uuid,
        step=body.step,
        user_data=body.user_data,
    )
    return BotStateResponse(
        telegram_id=row.telegram_id,
        agency_id=str(row.agency_id),
        step=row.step,
        user_data=bot_state_service.parse_state_json(row.state_json),
    )


@internal_router.delete("/bot-state/{telegram_id}", status_code=status.HTTP_204_NO_CONTENT)
@internal_limit()
async def delete_bot_state(
    request: Request,
    telegram_id: str,
    agency_id: str,
    db: DbSession,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> None:
    _check_internal_key(x_internal_key)
    try:
        agency_uuid = uuid.UUID(agency_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid agency_id") from exc

    await bot_state_service.delete_state(
        db, telegram_id=telegram_id, agency_id=agency_uuid
    )
