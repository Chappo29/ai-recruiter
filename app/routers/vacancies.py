import base64
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from sqlalchemy import delete, func, select

from app.core.config import get_internal_api_key
from app.core.rate_limit import internal_limit
from app.deps import CurrentUser, DbSession
from app.models import Agency, Candidate, Screening, User, Vacancy
from app.schemas.candidate import ResumeUploadRequest, ResumeUploadResponse
from app.schemas.vacancy import (
    InternalVacancyItem,
    InternalVacancyListResponse,
    ParseHHRequest,
    ParseVacancyHHResponse,
    VacancyCreate,
    VacancyResponse,
    VacancyStatsResponse,
    VacancyStatusUpdate,
    VacancyUpdate,
)
from app.utils.name import extract_first_name
from app.services import hh_parser

router = APIRouter(prefix="/vacancies", tags=["vacancies"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])

RESUME_MEDIA_DIR = Path(__file__).resolve().parents[2] / "media" / "resumes"


def _check_internal_key(x_internal_key: str) -> None:
    if x_internal_key != get_internal_api_key():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.post("/", response_model=VacancyResponse, status_code=status.HTTP_201_CREATED)
async def create_vacancy(
    body: VacancyCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> Vacancy:
    vacancy = Vacancy(
        user_id=current_user.id,
        title=body.title,
        company=body.company.strip(),
        hh_url=body.hh_url,
        requirements=body.requirements,
        description=body.description,
        ai_screening_prompt=body.ai_screening_prompt,
    )
    db.add(vacancy)
    await db.commit()
    await db.refresh(vacancy)
    return vacancy


@router.post("/parse-hh", response_model=ParseVacancyHHResponse)
async def parse_vacancy_hh(
    body: ParseHHRequest,
    current_user: CurrentUser,
) -> ParseVacancyHHResponse:
    _ = current_user
    parsed = await hh_parser.parse_vacancy(str(body.hh_url))
    return ParseVacancyHHResponse(**parsed)


@internal_router.get("/vacancies/", response_model=InternalVacancyListResponse)
@internal_limit()
async def list_agency_vacancies_internal(
    request: Request,
    agency_id: UUID,
    db: DbSession,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> InternalVacancyListResponse:
    _check_internal_key(x_internal_key)

    agency_result = await db.execute(select(Agency).where(Agency.id == agency_id))
    agency = agency_result.scalar_one_or_none()
    if agency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")

    result = await db.execute(
        select(Vacancy)
        .where(
            Vacancy.user_id.in_(select(User.id).where(User.agency_id == agency_id)),
            Vacancy.status == "active",
            Vacancy.archived_at.is_(None),
        )
        .order_by(Vacancy.created_at.desc())
    )
    vacancies = list(result.scalars().all())

    return InternalVacancyListResponse(
        feedback_days=agency.feedback_days,
        vacancies=[
            InternalVacancyItem(
                id=v.id,
                title=v.title,
                company=v.company,
                requirements=v.requirements,
                description=v.description,
                ai_screening_prompt=v.ai_screening_prompt,
            )
            for v in vacancies
        ],
    )


@internal_router.post("/parse-hh", response_model=ParseVacancyHHResponse)
@internal_limit()
async def parse_hh_internal(
    request: Request,
    body: ParseHHRequest,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> ParseVacancyHHResponse:
    _check_internal_key(x_internal_key)
    parsed = await hh_parser.parse_vacancy(str(body.hh_url))
    return ParseVacancyHHResponse(**parsed)


@internal_router.post("/vacancies/get-or-create")
@internal_limit()
async def get_or_create_vacancy_internal(
    request: Request,
    body: dict[str, Any],
    db: DbSession,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> dict[str, str]:
    _check_internal_key(x_internal_key)

    hh_url = body.get("hh_url")
    agency_id_raw = body.get("agency_id")
    if not hh_url or not agency_id_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="hh_url and agency_id are required",
        )

    agency_id = (
        agency_id_raw
        if isinstance(agency_id_raw, uuid.UUID)
        else uuid.UUID(str(agency_id_raw))
    )

    result = await db.execute(
        select(Vacancy).where(
            Vacancy.hh_url == hh_url,
            Vacancy.user_id.in_(
                select(User.id).where(User.agency_id == agency_id)
            ),
        )
    )
    vacancy = result.scalar_one_or_none()

    if vacancy:
        return {"id": str(vacancy.id)}

    user_result = await db.execute(
        select(User).where(User.agency_id == agency_id).limit(1)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency has no users",
        )

    company = (body.get("company") or "").strip() or "Не указана"
    vacancy = Vacancy(
        user_id=user.id,
        title=body.get("title") or "Без названия",
        company=company,
        hh_url=hh_url,
        requirements=body.get("requirements"),
        description=body.get("description"),
        ai_screening_prompt=body.get("ai_screening_prompt"),
        status="active",
    )
    db.add(vacancy)
    await db.commit()
    await db.refresh(vacancy)
    return {"id": str(vacancy.id)}


@internal_router.post("/candidates/")
@internal_limit()
async def create_candidate_internal(
    request: Request,
    body: dict[str, Any],
    db: DbSession,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> dict[str, str]:
    _check_internal_key(x_internal_key)

    telegram_id = body.get("telegram_id")
    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="telegram_id is required",
        )

    result = await db.execute(
        select(Candidate).where(Candidate.telegram_id == str(telegram_id))
    )
    candidate = result.scalar_one_or_none()

    full_name = body.get("full_name")
    first_name = body.get("first_name")
    if full_name and not first_name:
        first_name = extract_first_name(full_name)
    if full_name:
        from app.utils.name import normalize_full_name

        full_name = normalize_full_name(str(full_name))
        if not first_name:
            first_name = extract_first_name(full_name)

    if candidate:
        if full_name:
            candidate.full_name = full_name
            candidate.first_name = first_name
        if body.get("resume_text"):
            candidate.resume_text = body.get("resume_text")
        if body.get("hh_url"):
            candidate.hh_url = body.get("hh_url")
        await db.commit()
        await db.refresh(candidate)
        return {"id": str(candidate.id)}

    candidate = Candidate(
        full_name=full_name,
        first_name=first_name,
        telegram_id=str(telegram_id),
        hh_url=body.get("hh_url"),
        resume_text=body.get("resume_text"),
    )
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)
    return {"id": str(candidate.id)}


@internal_router.post(
    "/candidates/upload-resume",
    response_model=ResumeUploadResponse,
)
@internal_limit()
async def upload_candidate_resume(
    request: Request,
    body: ResumeUploadRequest,
    db: DbSession,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> ResumeUploadResponse:
    _check_internal_key(x_internal_key)

    result = await db.execute(
        select(Candidate).where(Candidate.id == body.candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    filename = (body.filename or "resume.pdf").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed",
        )

    try:
        file_bytes = base64.b64decode(body.file_base64, validate=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 file data",
        ) from exc

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )

    RESUME_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    candidate_id = str(body.candidate_id)
    file_path_rel = f"/media/resumes/{candidate_id}.pdf"
    file_path_abs = RESUME_MEDIA_DIR / f"{candidate_id}.pdf"

    with open(file_path_abs, "wb") as f:
        f.write(file_bytes)

    candidate.resume_file_path = file_path_rel
    await db.commit()

    return ResumeUploadResponse(file_path=file_path_rel)


@router.get("/", response_model=list[VacancyResponse])
async def list_vacancies(
    db: DbSession,
    current_user: CurrentUser,
    status: str | None = Query(default=None, description="Filter: active, archived, etc."),
) -> list[Vacancy]:
    query = select(Vacancy).where(Vacancy.user_id == current_user.id)
    if status == "archived":
        query = query.where(Vacancy.status == "archived")
    else:
        query = query.where(Vacancy.status != "archived")
    result = await db.execute(query.order_by(Vacancy.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{vacancy_id}", response_model=VacancyResponse)
async def get_vacancy(
    vacancy_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Vacancy:
    result = await db.execute(
        select(Vacancy).where(
            Vacancy.id == vacancy_id,
            Vacancy.user_id == current_user.id,
        )
    )
    vacancy = result.scalar_one_or_none()
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")
    return vacancy


@router.patch("/{vacancy_id}/status", response_model=VacancyResponse)
async def update_vacancy_status(
    vacancy_id: UUID,
    body: VacancyStatusUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Vacancy:
    result = await db.execute(
        select(Vacancy).where(
            Vacancy.id == vacancy_id,
            Vacancy.user_id == current_user.id,
        )
    )
    vacancy = result.scalar_one_or_none()
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")

    vacancy.status = body.status
    await db.commit()
    await db.refresh(vacancy)
    return vacancy


@router.patch("/{vacancy_id}", response_model=VacancyResponse)
async def update_vacancy(
    vacancy_id: UUID,
    body: VacancyUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Vacancy:
    result = await db.execute(
        select(Vacancy).where(
            Vacancy.id == vacancy_id,
            Vacancy.user_id == current_user.id,
        )
    )
    vacancy = result.scalar_one_or_none()
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")

    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "company" and value is not None:
            value = value.strip()
        setattr(vacancy, key, value)
    await db.commit()
    await db.refresh(vacancy)
    return vacancy


@router.patch("/{vacancy_id}/archive", response_model=VacancyResponse)
async def archive_vacancy(
    vacancy_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Vacancy:
    result = await db.execute(
        select(Vacancy).where(
            Vacancy.id == vacancy_id,
            Vacancy.user_id == current_user.id,
        )
    )
    vacancy = result.scalar_one_or_none()
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")

    vacancy.status = "archived"
    vacancy.archived_at = func.now()
    await db.commit()
    await db.refresh(vacancy)
    return vacancy


@router.delete("/{vacancy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vacancy(
    vacancy_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    result = await db.execute(
        select(Vacancy).where(
            Vacancy.id == vacancy_id,
            Vacancy.user_id == current_user.id,
        )
    )
    vacancy = result.scalar_one_or_none()
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")

    await db.execute(delete(Vacancy).where(Vacancy.id == vacancy_id))
    await db.commit()


@router.get("/{vacancy_id}/stats", response_model=VacancyStatsResponse)
async def get_vacancy_stats(
    vacancy_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> VacancyStatsResponse:
    await _get_owned_vacancy(db, vacancy_id, current_user)

    result = await db.execute(
        select(Screening.status, func.count())
        .where(Screening.vacancy_id == vacancy_id)
        .group_by(Screening.status)
    )
    counts = {row[0]: row[1] for row in result.all()}
    pending = counts.get("pending", 0)
    forwarded = counts.get("forwarded", 0)
    rejected = counts.get("rejected", 0)
    return VacancyStatsResponse(
        pending=pending,
        forwarded=forwarded,
        rejected=rejected,
        total=pending + forwarded + rejected,
    )


async def _get_owned_vacancy(db: DbSession, vacancy_id: UUID, user: CurrentUser) -> Vacancy:
    result = await db.execute(
        select(Vacancy).where(
            Vacancy.id == vacancy_id,
            Vacancy.user_id == user.id,
        )
    )
    vacancy = result.scalar_one_or_none()
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")
    return vacancy
