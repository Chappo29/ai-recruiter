"""Audit logging for AI-assisted hiring decisions."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIDecisionLog
from app.utils.json_fields import dump_json_text

logger = logging.getLogger(__name__)


async def log_ai_decision(
    db: AsyncSession,
    *,
    screening_id: UUID,
    decision_type: str,
    actor_type: str = "ai",
    agency_id: UUID | None = None,
    actor_id: UUID | None = None,
    ai_score: int | None = None,
    ai_verdict: str | None = None,
    reasoning: dict[str, Any] | str | None = None,
    human_override: bool = False,
) -> AIDecisionLog:
    """
    Persist an auditable record of an AI or human hiring decision.

    Failures are logged but do not block the main workflow.
    """
    reasoning_text: str | None
    if isinstance(reasoning, dict):
        reasoning_text = dump_json_text(reasoning)
    else:
        reasoning_text = reasoning

    entry = AIDecisionLog(
        screening_id=screening_id,
        agency_id=agency_id,
        decision_type=decision_type,
        actor_type=actor_type,
        actor_id=actor_id,
        ai_score=ai_score,
        ai_verdict=ai_verdict,
        reasoning=reasoning_text,
        human_override=human_override,
    )
    db.add(entry)
    try:
        await db.flush()
    except Exception:
        logger.exception(
            "Failed to write AI audit log for screening %s (%s)",
            screening_id,
            decision_type,
        )
        return entry
    return entry
