"""Agency-scoped access checks for multi-tenant resources."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Candidate, Screening, User, Vacancy


async def get_agency_vacancy(
    db: AsyncSession, vacancy_id: UUID, agency_id: UUID
) -> Vacancy:
    result = await db.execute(
        select(Vacancy)
        .join(User, Vacancy.user_id == User.id)
        .where(Vacancy.id == vacancy_id, User.agency_id == agency_id)
    )
    vacancy = result.scalar_one_or_none()
    if vacancy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found"
        )
    return vacancy


async def get_agency_screening(
    db: AsyncSession, screening_id: UUID, agency_id: UUID
) -> Screening:
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .join(User, Vacancy.user_id == User.id)
        .options(joinedload(Screening.candidate), joinedload(Screening.vacancy))
        .where(Screening.id == screening_id, User.agency_id == agency_id)
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found"
        )
    return screening


async def get_agency_candidate(
    db: AsyncSession, candidate_id: UUID, agency_id: UUID
) -> Candidate:
    result = await db.execute(
        select(Candidate).where(
            Candidate.id == candidate_id,
            Candidate.agency_id == agency_id,
        )
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found"
        )
    return candidate


def agency_vacancy_filter(agency_id: UUID):
    """SQLAlchemy filter: vacancy belongs to agency."""
    return Vacancy.user_id.in_(
        select(User.id).where(User.agency_id == agency_id)
    )
