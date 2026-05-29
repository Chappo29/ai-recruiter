"""Vacancy rubric generation, approval, and retrieval."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Vacancy, VacancyRubric
from app.schemas.llm import RubricCompetency, RubricDraft
from app.services.llm_service import generate_rubric_draft
from app.utils.json_fields import dump_json_text, parse_json_text

logger = logging.getLogger(__name__)


def build_vacancy_text(vacancy: Vacancy) -> str:
    parts = [vacancy.title, vacancy.requirements, vacancy.description]
    text = "\n\n".join(p for p in parts if p)
    if vacancy.ai_screening_prompt:
        text = f"{text}\n\nВводные рекрутера:\n{vacancy.ai_screening_prompt}"
    return text


def normalize_rubric_json(rubric_json: dict[str, Any]) -> dict[str, Any]:
    """Normalize competency weights to sum 1.0."""
    competencies = rubric_json.get("competencies") or []
    if not competencies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rubric must contain at least one competency",
        )

    validated = [RubricCompetency.model_validate(c).model_dump() for c in competencies]
    total = sum(float(c.get("weight") or 0) for c in validated)
    if total <= 0:
        equal = 1.0 / len(validated)
        for comp in validated:
            comp["weight"] = equal
    elif abs(total - 1.0) > 0.01:
        for comp in validated:
            comp["weight"] = float(comp["weight"]) / total

    return {
        **rubric_json,
        "competencies": validated,
    }


async def _next_version(db: AsyncSession, vacancy_id: UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(VacancyRubric.version), 0)).where(
            VacancyRubric.vacancy_id == vacancy_id
        )
    )
    current = result.scalar_one()
    return int(current) + 1


async def generate_draft_rubric(
    db: AsyncSession,
    *,
    vacancy: Vacancy,
    user: User,
) -> VacancyRubric:
    vacancy_text = build_vacancy_text(vacancy)
    try:
        draft: RubricDraft = await generate_rubric_draft(
            vacancy_text, vacancy_id=str(vacancy.id)
        )
    except Exception:
        logger.exception("Rubric generation failed for vacancy %s", vacancy.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate rubric",
        ) from None

    rubric_data = normalize_rubric_json(draft.model_dump())
    version = await _next_version(db, vacancy.id)
    rubric = VacancyRubric(
        vacancy_id=vacancy.id,
        version=version,
        status="draft",
        rubric_json=dump_json_text(rubric_data),
        created_by=user.id,
    )
    db.add(rubric)
    await db.commit()
    await db.refresh(rubric)
    return rubric


async def get_latest_rubric(
    db: AsyncSession, vacancy_id: UUID, *, prefer_approved: bool = True
) -> VacancyRubric | None:
    if prefer_approved:
        result = await db.execute(
            select(VacancyRubric)
            .where(
                VacancyRubric.vacancy_id == vacancy_id,
                VacancyRubric.status == "approved",
            )
            .order_by(VacancyRubric.version.desc())
            .limit(1)
        )
        approved = result.scalar_one_or_none()
        if approved is not None:
            return approved

    result = await db.execute(
        select(VacancyRubric)
        .where(VacancyRubric.vacancy_id == vacancy_id)
        .order_by(VacancyRubric.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_rubric_overview(
    db: AsyncSession, vacancy_id: UUID
) -> tuple[VacancyRubric | None, VacancyRubric | None]:
    """Return (latest_draft, approved_rubric)."""
    draft_result = await db.execute(
        select(VacancyRubric)
        .where(
            VacancyRubric.vacancy_id == vacancy_id,
            VacancyRubric.status == "draft",
        )
        .order_by(VacancyRubric.version.desc())
        .limit(1)
    )
    draft = draft_result.scalar_one_or_none()

    approved_result = await db.execute(
        select(VacancyRubric)
        .where(
            VacancyRubric.vacancy_id == vacancy_id,
            VacancyRubric.status == "approved",
        )
        .order_by(VacancyRubric.version.desc())
        .limit(1)
    )
    approved = approved_result.scalar_one_or_none()
    return draft, approved


async def get_active_rubric(
    db: AsyncSession, vacancy: Vacancy, user: User | None = None
) -> VacancyRubric:
    """Return approved rubric or auto-generate draft on first screening (PR #3)."""
    rubric = await get_latest_rubric(db, vacancy.id, prefer_approved=True)
    if rubric is not None:
        return rubric

    rubric = await get_latest_rubric(db, vacancy.id, prefer_approved=False)
    if rubric is not None:
        return rubric

    if user is None:
        result = await db.execute(select(User).where(User.id == vacancy.user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="Vacancy owner not found")

    return await generate_draft_rubric(db, vacancy=vacancy, user=user)


async def update_draft_rubric(
    db: AsyncSession,
    *,
    rubric: VacancyRubric,
    rubric_json: dict,
) -> VacancyRubric:
    if rubric.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft rubrics can be edited",
        )
    normalized = normalize_rubric_json(rubric_json)
    rubric.rubric_json = dump_json_text(normalized)
    await db.commit()
    await db.refresh(rubric)
    return rubric


async def approve_rubric(
    db: AsyncSession,
    *,
    rubric: VacancyRubric,
    user: User,
) -> VacancyRubric:
    if rubric.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft rubrics can be approved",
        )

    result = await db.execute(
        select(VacancyRubric).where(
            VacancyRubric.vacancy_id == rubric.vacancy_id,
            VacancyRubric.status == "approved",
        )
    )
    for old in result.scalars().all():
        old.status = "archived"

    rubric.status = "approved"
    rubric.approved_by = user.id
    rubric.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(rubric)
    return rubric


def parse_rubric_json(rubric: VacancyRubric) -> dict:
    parsed = parse_json_text(rubric.rubric_json)
    return parsed if isinstance(parsed, dict) else {}
