from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models import Candidate, Screening, Vacancy
from app.schemas.candidate import (
    CandidateCreate,
    CandidateResponse,
    ParseHHRequest,
    ParseResumeHHResponse,
)
from app.services import hh_parser

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("/", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    body: CandidateCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> Candidate:
    _ = current_user
    candidate = Candidate(
        full_name=body.full_name,
        telegram_id=body.telegram_id,
        hh_url=body.hh_url,
        resume_text=body.resume_text,
    )
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)
    return candidate


@router.post("/parse-hh", response_model=ParseResumeHHResponse)
async def parse_resume_hh(
    body: ParseHHRequest,
    current_user: CurrentUser,
) -> ParseResumeHHResponse:
    _ = current_user
    parsed = await hh_parser.parse_resume(str(body.hh_url))
    return ParseResumeHHResponse(**parsed)


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Candidate:
    result = await db.execute(
        select(Candidate)
        .join(Screening, Screening.candidate_id == Candidate.id)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .where(
            Candidate.id == candidate_id,
            Vacancy.user_id == current_user.id,
        )
        .limit(1)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidate
