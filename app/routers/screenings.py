import logging
import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.config import get_internal_api_key
from app.database import async_session_factory
from app.deps import CurrentUser, DbSession
from app.models import CandidateAnswer, Screening, Vacancy
from app.schemas.question import AnswerResponse
from app.schemas.screening import (
    AnswersEvaluationResponse,
    ScreeningCreate,
    ScreeningResponse,
    ScreeningStats,
    ScreeningStatusUpdate,
)
from app.services import screening_service
from app.utils.display_verdict import display_verdict_for
from app.utils.screening_response import compute_screening_indices, to_screening_response
from bot import manager as bot_manager

router = APIRouter(prefix="/screenings", tags=["screenings"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])

logger = logging.getLogger(__name__)


def _check_internal_key(x_internal_key: str) -> None:
    if x_internal_key != get_internal_api_key():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


async def _run_screening_background(screening_id: UUID) -> None:
    async with async_session_factory() as db:
        try:
            await screening_service.complete_screening(db, screening_id)
        except Exception:
            logger.exception("Background screening failed for %s", screening_id)


async def _load_screening_with_candidate(
    db: DbSession, screening_id: UUID
) -> Screening:
    result = await db.execute(
        select(Screening)
        .options(joinedload(Screening.candidate))
        .where(Screening.id == screening_id)
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")
    return screening


@router.post("/", response_model=ScreeningResponse, status_code=status.HTTP_201_CREATED)
async def start_screening(
    body: ScreeningCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ScreeningResponse:
    try:
        screening = await screening_service.run_and_save_screening(
            db,
            vacancy_id=body.vacancy_id,
            candidate_id=body.candidate_id,
            user=current_user,
        )
    except Exception as exc:
        logger.exception("Screening failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM screening failed: {exc}",
        ) from exc
    screening = await _load_screening_with_candidate(db, screening.id)
    return to_screening_response(screening, candidate=screening.candidate)


@internal_router.post("/screenings/", response_model=ScreeningResponse)
async def create_screening_internal(
    body: dict[str, Any],
    db: DbSession,
    background_tasks: BackgroundTasks,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> ScreeningResponse:
    _check_internal_key(x_internal_key)

    vacancy_id_raw = body.get("vacancy_id")
    candidate_id_raw = body.get("candidate_id")
    if not vacancy_id_raw or not candidate_id_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vacancy_id and candidate_id are required",
        )

    vacancy_id = (
        vacancy_id_raw
        if isinstance(vacancy_id_raw, uuid.UUID)
        else UUID(str(vacancy_id_raw))
    )
    candidate_id = (
        candidate_id_raw
        if isinstance(candidate_id_raw, uuid.UUID)
        else UUID(str(candidate_id_raw))
    )

    run_llm = body.get("run_llm", True)
    if isinstance(run_llm, str):
        run_llm = run_llm.lower() not in ("false", "0", "no")

    screening = await screening_service.create_pending_screening(
        db,
        vacancy_id=vacancy_id,
        candidate_id=candidate_id,
    )
    if run_llm:
        background_tasks.add_task(_run_screening_background, screening.id)
    screening = await _load_screening_with_candidate(db, screening.id)
    return to_screening_response(screening, candidate=screening.candidate)


@internal_router.post("/screenings/{screening_id}/complete")
async def complete_screening_internal(
    screening_id: UUID,
    background_tasks: BackgroundTasks,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> dict[str, str]:
    _check_internal_key(x_internal_key)
    background_tasks.add_task(_run_screening_background, screening_id)
    return {"status": "queued"}


@router.get("/stats", response_model=list[ScreeningStats])
async def get_screening_stats(
    db: DbSession,
    current_user: CurrentUser,
) -> list[ScreeningStats]:
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .where(Vacancy.user_id == current_user.id)
    )
    screenings = list(result.scalars().all())

    by_vacancy: dict[UUID, ScreeningStats] = {}
    for screening in screenings:
        vid = screening.vacancy_id
        if vid not in by_vacancy:
            by_vacancy[vid] = ScreeningStats(vacancy_id=vid)
        stats = by_vacancy[vid]
        stats.total += 1
        dv = display_verdict_for(screening) or ""
        dv = dv.lower()
        if dv == "fit":
            stats.fit += 1
        elif dv == "maybe":
            stats.maybe += 1
        elif dv == "reject":
            stats.reject += 1
        elif dv == "pending":
            stats.pending += 1

    return list(by_vacancy.values())


@router.get("/recent", response_model=list[ScreeningResponse])
async def list_recent_screenings(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = 5,
) -> list[ScreeningResponse]:
    """Latest screening per candidate (newest attempt wins)."""
    capped = max(1, min(limit, 20))
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .options(joinedload(Screening.candidate))
        .where(Vacancy.user_id == current_user.id)
        .order_by(Screening.created_at.desc())
        .limit(capped * 10)
    )
    all_rows = list(result.scalars().unique().all())
    seen_candidates: set[UUID] = set()
    unique: list[Screening] = []
    for screening in all_rows:
        if screening.candidate_id in seen_candidates:
            continue
        seen_candidates.add(screening.candidate_id)
        unique.append(screening)
        if len(unique) >= capped:
            break
    return [
        to_screening_response(screening, candidate=screening.candidate)
        for screening in unique
    ]


@router.post("/{screening_id}/run-llm", response_model=ScreeningResponse)
async def rerun_screening_llm(
    screening_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> ScreeningResponse:
    """Queue or re-queue LLM analysis for pending/failed screenings."""
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .options(joinedload(Screening.candidate))
        .where(
            Screening.id == screening_id,
            Vacancy.user_id == current_user.id,
        )
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")

    if screening.status not in ("pending", "failed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screening is already completed",
        )

    screening.status = "pending"
    await db.commit()
    background_tasks.add_task(_run_screening_background, screening.id)
    screening = await _load_screening_with_candidate(db, screening.id)
    return to_screening_response(screening, candidate=screening.candidate)


@router.get("/vacancy/{vacancy_id}", response_model=list[ScreeningResponse])
async def list_screenings_for_vacancy(
    vacancy_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[ScreeningResponse]:
    await screening_service.get_user_vacancy(db, vacancy_id, current_user)

    result = await db.execute(
        select(Screening)
        .where(Screening.vacancy_id == vacancy_id)
        .options(joinedload(Screening.candidate))
        .order_by(Screening.score.desc().nulls_last(), Screening.created_at.desc())
    )
    screenings = list(result.scalars().unique().all())
    indices = compute_screening_indices(screenings)
    return [
        to_screening_response(
            screening,
            candidate=screening.candidate,
            screening_index=indices.get(screening.id),
        )
        for screening in screenings
    ]


@router.get("/candidate/{candidate_id}/history", response_model=list[ScreeningResponse])
async def list_candidate_screening_history(
    candidate_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[ScreeningResponse]:
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .options(joinedload(Screening.candidate))
        .where(
            Screening.candidate_id == candidate_id,
            Vacancy.user_id == current_user.id,
        )
        .order_by(Screening.created_at.desc())
    )
    screenings = list(result.scalars().unique().all())
    indices = compute_screening_indices(screenings)
    return [
        to_screening_response(
            screening,
            candidate=screening.candidate,
            screening_index=indices.get(screening.id),
        )
        for screening in screenings
    ]


@router.get("/{screening_id}/answers", response_model=list[AnswerResponse])
async def list_screening_answers(
    screening_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[AnswerResponse]:
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .where(
            Screening.id == screening_id,
            Vacancy.user_id == current_user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")

    answers_result = await db.execute(
        select(CandidateAnswer)
        .where(CandidateAnswer.screening_id == screening_id)
        .options(joinedload(CandidateAnswer.question))
        .order_by(CandidateAnswer.created_at.asc())
    )
    answers = answers_result.scalars().unique().all()

    return [
        AnswerResponse(
            id=answer.id,
            screening_id=answer.screening_id,
            question_id=answer.question_id,
            question_text=answer.question.text if answer.question else None,
            answer_text=answer.answer_text,
            created_at=answer.created_at,
        )
        for answer in answers
    ]


@router.post("/{screening_id}/evaluate-answers", response_model=AnswersEvaluationResponse)
async def evaluate_screening_answers(
    screening_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> AnswersEvaluationResponse:
    try:
        screening, evaluation = await screening_service.evaluate_screening_answers(
            db, screening_id, current_user
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Answer evaluation failed for screening %s", screening_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM evaluation failed: {exc}",
        ) from exc

    _ = screening
    return AnswersEvaluationResponse(
        answers_summary=evaluation.get("answers_summary"),
        answers_score=evaluation.get("answers_score"),
        strong_answers=evaluation.get("strong_answers") or [],
        weak_answers=evaluation.get("weak_answers") or [],
    )


@router.post("/{screening_id}/reject", response_model=ScreeningResponse)
async def reject_screening(
    screening_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ScreeningResponse:
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .options(joinedload(Screening.candidate))
        .where(
            Screening.id == screening_id,
            Vacancy.user_id == current_user.id,
        )
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")

    candidate = screening.candidate
    if candidate is None or not candidate.telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidate has no Telegram ID",
        )

    full_name = candidate.full_name or "Кандидат"
    candidate_name = full_name.split()[0] if full_name else "Кандидат"
    agency_id = str(current_user.agency_id)

    try:
        await bot_manager.send_rejection(
            agency_id, candidate.telegram_id, candidate_name
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to send rejection for screening %s", screening_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send Telegram message",
        ) from exc

    screening.status = "rejected"
    await db.commit()
    await db.refresh(screening)

    return to_screening_response(screening, candidate=candidate)


@router.get("/{screening_id}", response_model=ScreeningResponse)
async def get_screening(
    screening_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ScreeningResponse:
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .options(joinedload(Screening.candidate))
        .where(
            Screening.id == screening_id,
            Vacancy.user_id == current_user.id,
        )
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")
    return to_screening_response(screening, candidate=screening.candidate)


@router.patch("/{screening_id}/status", response_model=ScreeningResponse)
async def update_screening_status(
    screening_id: UUID,
    body: ScreeningStatusUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ScreeningResponse:
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .options(joinedload(Screening.candidate))
        .where(
            Screening.id == screening_id,
            Vacancy.user_id == current_user.id,
        )
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")

    screening.status = body.status
    await db.commit()
    screening = await _load_screening_with_candidate(db, screening.id)
    return to_screening_response(screening, candidate=screening.candidate)
