"""Persist and restore bot dialog state via backend internal API."""

import logging
from typing import Any

import httpx

from app.core.config import get_internal_api_key
from app.services.bot_state_service import infer_step, serialize_user_data

logger = logging.getLogger(__name__)

STEP_TO_CONV = {
    "wait_vacancy": 0,
    "wait_resume": 1,
    "interview": 1,
    "finished": 1,
}


def _headers() -> dict[str, str]:
    return {"X-Internal-Key": get_internal_api_key()}


async def save_bot_session(
    *,
    backend_url: str,
    agency_id: str,
    telegram_id: str,
    user_data: dict[str, Any],
    step: str | None = None,
) -> None:
    resolved_step = step or infer_step(user_data)
    payload = {
        "agency_id": agency_id,
        "step": resolved_step,
        "user_data": serialize_user_data(user_data),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                f"{backend_url.rstrip('/')}/internal/bot-state/{telegram_id}",
                headers=_headers(),
                json=payload,
            )
            response.raise_for_status()
    except Exception:
        logger.warning(
            "Failed to save bot session telegram_id=%s step=%s",
            telegram_id,
            resolved_step,
            exc_info=True,
        )


async def load_bot_session(
    *,
    backend_url: str,
    agency_id: str,
    telegram_id: str,
) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{backend_url.rstrip('/')}/internal/bot-state/{telegram_id}",
                headers=_headers(),
                params={"agency_id": agency_id},
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            if not data:
                return None
            return data
    except Exception:
        logger.warning(
            "Failed to load bot session telegram_id=%s",
            telegram_id,
            exc_info=True,
        )
        return None


async def clear_bot_session(
    *,
    backend_url: str,
    agency_id: str,
    telegram_id: str,
) -> None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                f"{backend_url.rstrip('/')}/internal/bot-state/{telegram_id}",
                headers=_headers(),
                params={"agency_id": agency_id},
            )
            if response.status_code not in (204, 404):
                response.raise_for_status()
    except Exception:
        logger.warning(
            "Failed to clear bot session telegram_id=%s",
            telegram_id,
            exc_info=True,
        )


def conversation_state_for_step(step: str) -> int | None:
    return STEP_TO_CONV.get(step)
