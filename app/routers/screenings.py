import logging
import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.config import get_internal_api_key
from app.core.rate_limit import internal_limit
from app.database import async_session_factory
from app.deps import CurrentUser, DbSession
from app.models import Screening, Vacancy
from app.schemas.screening import (
    SCREENING_STATUSES,
    ScreeningCreate,
    ScreeningResponse,
    ScreeningStats,
    ScreeningStatusUpdate,
)
from app.services import screening_service
from app.utils.display_verdict import display_verdict_for
from app.utils.name import extract_first_name
from app.utils.screening_response import compute_screening_indices, to_screening_response
from bot.outbound import send_rejection

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


async def _load_screening_with_relations(db: DbSession, screening_id: UUID) -> Screening:
    result = await db.execute(
        select(Screening)
        .options(joinedload(Screening.candidate), joinedload(Screening.vacancy))
        .where(Screening.id == screening_id)
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")
    return screening


def _to_response(screening: Screening, *, screening_index: int | None = None) -> ScreeningResponse:
    return to_screening_response(
        screening,
        candidate=screening.candidate,
        vacancy=screening.vacancy,
        screening_index=screening_index,
    )


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
    screening = await _load_screening_with_relations(db, screening.id)
    return _to_response(screening)


@internal_router.post("/screenings/", response_model=ScreeningResponse)
@internal_limit()
async def create_screening_internal(
    request: Request,
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
        vacancy_id_raw if isinstance(vacancy_id_raw, uuid.UUID) else UUID(str(vacancy_id_raw))
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
    screening = await _load_screening_with_relations(db, screening.id)
    return _to_response(screening)


@internal_router.post("/screenings/{screening_id}/complete")
@internal_limit()
async def complete_screening_internal(
    request: Request,
    screening_id: UUID,
    background_tasks: BackgroundTasks,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> dict[str, str]:
    _check_internal_key(x_internal_key)
    background_tasks.add_task(_run_screening_background, screening_id)
    return {"status": "queued"}


@internal_router.patch("/screenings/{screening_id}/dialog")
@internal_limit()
async def append_screening_dialog_internal(
    request: Request,
    screening_id: UUID,
    body: dict[str, Any],
    db: DbSession,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> dict[str, str]:
    _check_internal_key(x_internal_key)
    messages = body.get("messages") or []
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages must be a list")
    await screening_service.append_dialog_messages(db, screening_id, messages)
    return {"status": "ok"}


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
        st = (screening.status or "pending").lower()
        if st == "pending":
            stats.pending += 1
        elif st == "forwarded":
            stats.forwarded += 1
        elif st == "rejected":
            stats.rejected += 1

    return list(by_vacancy.values())


@router.get("/recent", response_model=list[ScreeningResponse])
async def list_recent_screenings(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = 5,
) -> list[ScreeningResponse]:
    capped = max(1, min(limit, 20))
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .options(joinedload(Screening.candidate), joinedload(Screening.vacancy))
        .where(Vacancy.user_id == current_user.id)
        .order_by(Screening.created_at.desc())
        .limit(capped * 10)
    )
    all_rows = list(result.scalars().unique().all())
    indices = compute_screening_indices(all_rows)
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
        _to_response(s, screening_index=indices.get(s.id)) for s in unique
    ]


@router.post("/{screening_id}/run-llm", response_model=ScreeningResponse)
async def rerun_screening_llm(
    screening_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> ScreeningResponse:
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .options(joinedload(Screening.candidate), joinedload(Screening.vacancy))
        .where(
            Screening.id == screening_id,
            Vacancy.user_id == current_user.id,
        )
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")

    background_tasks.add_task(_run_screening_background, screening.id)
    screening = await _load_screening_with_relations(db, screening.id)
    return _to_response(screening)


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
        .options(joinedload(Screening.candidate), joinedload(Screening.vacancy))
        .order_by(Screening.created_at.desc())
    )
    screenings = list(result.scalars().unique().all())
    indices = compute_screening_indices(screenings)
    return [
        _to_response(screening, screening_index=indices.get(screening.id))
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
        .options(joinedload(Screening.candidate), joinedload(Screening.vacancy))
        .where(
            Screening.candidate_id == candidate_id,
            Vacancy.user_id == current_user.id,
        )
        .order_by(Screening.created_at.desc())
    )
    screenings = list(result.scalars().unique().all())
    indices = compute_screening_indices(screenings)
    return [
        _to_response(screening, screening_index=indices.get(screening.id))
        for screening in screenings
    ]


@router.post("/{screening_id}/reject", response_model=ScreeningResponse)
async def reject_screening(
    screening_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ScreeningResponse:
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .options(joinedload(Screening.candidate), joinedload(Screening.vacancy))
        .where(
            Screening.id == screening_id,
            Vacancy.user_id == current_user.id,
        )
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")

    candidate = screening.candidate
    vacancy = screening.vacancy
    if candidate is None or not candidate.telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidate has no Telegram ID",
        )

    candidate_name = (
        candidate.first_name
        or extract_first_name(candidate.full_name)
        or "Кандидат"
    )
    vacancy_title = vacancy.title if vacancy else "вакансию"

    try:
        await send_rejection(
            db,
            current_user.agency_id,
            candidate.telegram_id,
            candidate_name,
            vacancy_title,
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
    screening = await _load_screening_with_relations(db, screening.id)
    return _to_response(screening)


@router.get("/{screening_id}", response_model=ScreeningResponse)
async def get_screening(
    screening_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ScreeningResponse:
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .options(joinedload(Screening.candidate), joinedload(Screening.vacancy))
        .where(
            Screening.id == screening_id,
            Vacancy.user_id == current_user.id,
        )
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")
    return _to_response(screening)


@router.post("/{screening_id}/reanalyze", response_model=ScreeningResponse)
async def reanalyze_screening(
    screening_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> ScreeningResponse:
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .options(joinedload(Screening.candidate), joinedload(Screening.vacancy))
        .where(
            Screening.id == screening_id,
            Vacancy.user_id == current_user.id,
        )
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")

    screening.summary = None
    screening.score = None
    await db.commit()

    background_tasks.add_task(_run_screening_background, screening_id)
    screening = await _load_screening_with_relations(db, screening_id)
    return _to_response(screening)


@router.patch("/{screening_id}/status", response_model=ScreeningResponse)
async def update_screening_status(
    screening_id: UUID,
    body: ScreeningStatusUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ScreeningResponse:
    if body.status not in SCREENING_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid screening status")

    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .options(joinedload(Screening.candidate), joinedload(Screening.vacancy))
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
    screening = await _load_screening_with_relations(db, screening.id)
    return _to_response(screening)
