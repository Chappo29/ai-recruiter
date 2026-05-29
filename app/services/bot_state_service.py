"""Persist and restore Telegram bot conversation state."""

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotConversationState

logger = logging.getLogger(__name__)

PERSIST_KEYS = (
    "vacancy_id",
    "vacancy_title",
    "vacancy_company",
    "ai_screening_prompt",
    "vacancy_text",
    "candidate_id",
    "screening_id",
    "first_name",
    "full_name",
    "dialog",
    "interview_turns",
    "interview_questions",
    "question_index",
    "awaiting_questions",
    "conversation_finished",
    "processing_resume",
    "feedback_days",
)

VALID_STEPS = frozenset({"wait_vacancy", "wait_resume", "interview", "finished"})


def infer_step(user_data: dict[str, Any]) -> str:
    if user_data.get("conversation_finished"):
        return "finished"
    if user_data.get("awaiting_questions"):
        return "interview"
    if user_data.get("vacancy_id"):
        return "wait_resume"
    return "wait_vacancy"


def serialize_user_data(user_data: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in PERSIST_KEYS:
        if key in user_data:
            payload[key] = user_data[key]
    return payload


def deserialize_user_data(raw: dict[str, Any]) -> dict[str, Any]:
    return {key: raw[key] for key in PERSIST_KEYS if key in raw}


async def get_state(
    db: AsyncSession,
    *,
    telegram_id: str,
    agency_id: uuid.UUID,
) -> BotConversationState | None:
    result = await db.execute(
        select(BotConversationState).where(
            BotConversationState.telegram_id == telegram_id,
            BotConversationState.agency_id == agency_id,
        )
    )
    return result.scalar_one_or_none()


async def save_state(
    db: AsyncSession,
    *,
    telegram_id: str,
    agency_id: uuid.UUID,
    step: str,
    user_data: dict[str, Any],
) -> BotConversationState:
    if step not in VALID_STEPS:
        raise ValueError(f"Invalid bot step: {step}")

    payload = serialize_user_data(user_data)
    state_json = json.dumps(payload, ensure_ascii=False, default=str)

    row = await get_state(db, telegram_id=telegram_id, agency_id=agency_id)
    if row is None:
        row = BotConversationState(
            telegram_id=telegram_id,
            agency_id=agency_id,
            step=step,
            state_json=state_json,
        )
        db.add(row)
    else:
        row.step = step
        row.state_json = state_json

    await db.commit()
    await db.refresh(row)
    return row


async def delete_state(
    db: AsyncSession,
    *,
    telegram_id: str,
    agency_id: uuid.UUID,
) -> None:
    row = await get_state(db, telegram_id=telegram_id, agency_id=agency_id)
    if row is None:
        return
    await db.delete(row)
    await db.commit()


def parse_state_json(state_json: str) -> dict[str, Any]:
    try:
        raw = json.loads(state_json or "{}")
    except json.JSONDecodeError:
        logger.warning("Invalid bot state JSON, using empty dict")
        return {}
    if not isinstance(raw, dict):
        return {}
    return deserialize_user_data(raw)
