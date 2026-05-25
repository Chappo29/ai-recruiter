"""Stateless Telegram outbound messages via Bot API (any FastAPI worker)."""

import logging
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agency

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


async def get_bot_token(db: AsyncSession, agency_id: str | UUID) -> str:
    agency_uuid = agency_id if isinstance(agency_id, UUID) else UUID(str(agency_id))
    result = await db.execute(
        select(Agency.telegram_bot_token).where(Agency.id == agency_uuid)
    )
    token = result.scalar_one_or_none()
    if not token or not str(token).strip():
        raise RuntimeError("Telegram bot token not configured for agency")
    return str(token).strip()


async def send_message(
    db: AsyncSession,
    agency_id: str | UUID,
    telegram_id: str,
    text: str,
) -> None:
    token = await get_bot_token(db, agency_id)
    chat_id = int(str(telegram_id).strip())
    url = TELEGRAM_API.format(token=token, method="sendMessage")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json={"chat_id": chat_id, "text": text})
        response.raise_for_status()
        payload = response.json()
    if not payload.get("ok"):
        description = payload.get("description", "Telegram API error")
        logger.warning(
            "Telegram sendMessage failed agency=%s chat_id=%s: %s",
            agency_id,
            chat_id,
            description,
        )
        raise RuntimeError(description)


async def send_rejection(
    db: AsyncSession,
    agency_id: str | UUID,
    telegram_id: str,
    candidate_name: str,
    vacancy_title: str,
) -> None:
    text = (
        f"Здравствуйте, {candidate_name}!\n"
        f"К сожалению, после рассмотрения вашей кандидатуры на вакансию "
        f"{vacancy_title} мы приняли решение продолжить поиск с другими кандидатами.\n"
        "Это не значит, что вы плохой специалист — "
        "просто в этот раз не совпали требования.\n"
        "Желаем успехов в поиске! 🙏"
    )
    await send_message(db, agency_id, telegram_id, text)
