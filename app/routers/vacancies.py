import base64
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from sqlalchemy import delete, func, select

from app.core.internal_auth import verify_internal_key
from app.core.rate_limit import internal_limit, parse_hh_limit
from app.core.rbac import UserRole, require_role
from app.deps import CurrentUser, DbSession
from app.models import Agency, Candidate, Screening, User, Vacancy, VacancyRubric
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
from app.schemas.rubric import RubricOverviewResponse, RubricResponse, RubricUpdateRequest
from app.services import hh_parser, rubric_service
from app.services.agency_access import get_agency_candidate, get_agency_vacancy
from app.utils.file_validation import validate_pdf_file
from app.utils.name import extract_first_name

router = APIRouter(prefix="/vacancies", tags=["vacancies"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])

RESUME_MEDIA_DIR = Path(__file__).resolve().parents[2] / "media" / "resumes"


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
@parse_hh_limit()
async def parse_vacancy_hh(
    request: Request,
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
    verify_internal_key(x_internal_key)

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
    verify_internal_key(x_internal_key)
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
    verify_internal_key(x_internal_key)

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
    verify_internal_key(x_internal_key)

    telegram_id = body.get("telegram_id")
    agency_id_raw = body.get("agency_id")
    if not telegram_id or not agency_id_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="telegram_id and agency_id are required",
        )
    agency_id = UUID(str(agency_id_raw))

    agency_result = await db.execute(select(Agency).where(Agency.id == agency_id))
    if agency_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")

    full_name = body.get("full_name")
    first_name = body.get("first_name")
    if full_name and not first_name:
        first_name = extract_first_name(full_name)
    if full_name:
        from app.utils.name import normalize_full_name

        full_name = normalize_full_name(str(full_name))
        if not first_name:
            first_name = extract_first_name(full_name)

    # Each bot application gets its own candidate record so a new resume
    # cannot overwrite names/resumes on previous screenings.
    candidate = Candidate(
        agency_id=agency_id,
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
    verify_internal_key(x_internal_key)
    candidate = await get_agency_candidate(db, body.candidate_id, body.agency_id)

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

    # Validate file size and MIME type
    validate_pdf_file(file_bytes)

    RESUME_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{body.candidate_id}_{uuid.uuid4().hex[:12]}.pdf"
    file_path_rel = f"/media/resumes/{stored_name}"
    file_path_abs = RESUME_MEDIA_DIR / stored_name

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
    # Показываем все вакансии агентства (не только созданные текущим пользователем)
    query = select(Vacancy).where(
        Vacancy.user_id.in_(
            select(User.id).where(User.agency_id == current_user.agency_id)
        )
    )
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
    # Показываем вакансию, если она принадлежит агентству пользователя
    result = await db.execute(
        select(Vacancy)
        .join(User, Vacancy.user_id == User.id)
        .where(
            Vacancy.id == vacancy_id,
            User.agency_id == current_user.agency_id,
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
        select(Vacancy)
        .join(User, Vacancy.user_id == User.id)
        .where(
            Vacancy.id == vacancy_id,
            User.agency_id == current_user.agency_id,
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
        select(Vacancy)
        .join(User, Vacancy.user_id == User.id)
        .where(
            Vacancy.id == vacancy_id,
            User.agency_id == current_user.agency_id,
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
        select(Vacancy)
        .join(User, Vacancy.user_id == User.id)
        .where(
            Vacancy.id == vacancy_id,
            User.agency_id == current_user.agency_id,
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
    # Все сотрудники агентства могут удалять вакансии (не только admin)
    result = await db.execute(
        select(Vacancy)
        .join(User, Vacancy.user_id == User.id)
        .where(
            Vacancy.id == vacancy_id,
            User.agency_id == current_user.agency_id,
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
    # Проверяем, что вакансия принадлежит агентству пользователя
    vacancy_check = await db.execute(
        select(Vacancy)
        .join(User, Vacancy.user_id == User.id)
        .where(
            Vacancy.id == vacancy_id,
            User.agency_id == current_user.agency_id,
        )
    )
    if vacancy_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")

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


def _rubric_to_response(rubric: VacancyRubric) -> RubricResponse:
    from app.utils.json_fields import parse_json_text

    data = parse_json_text(rubric.rubric_json)
    return RubricResponse(
        id=rubric.id,
        vacancy_id=rubric.vacancy_id,
        version=rubric.version,
        status=rubric.status,
        rubric_json=data if isinstance(data, dict) else {},
        created_by=rubric.created_by,
        approved_by=rubric.approved_by,
        created_at=rubric.created_at,
        approved_at=rubric.approved_at,
    )


@router.get("/{vacancy_id}/rubric", response_model=RubricOverviewResponse)
async def get_vacancy_rubric(
    vacancy_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> RubricOverviewResponse:
    await get_agency_vacancy(db, vacancy_id, current_user.agency_id)
    draft, approved = await rubric_service.get_rubric_overview(db, vacancy_id)
    return RubricOverviewResponse(
        draft=_rubric_to_response(draft) if draft else None,
        approved=_rubric_to_response(approved) if approved else None,
    )


@router.post("/{vacancy_id}/rubric/generate", response_model=RubricResponse)
async def generate_vacancy_rubric(
    vacancy_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> RubricResponse:
    vacancy = await get_agency_vacancy(db, vacancy_id, current_user.agency_id)
    rubric = await rubric_service.generate_draft_rubric(
        db, vacancy=vacancy, user=current_user
    )
    return _rubric_to_response(rubric)


@router.put("/{vacancy_id}/rubric/{rubric_id}", response_model=RubricResponse)
async def update_vacancy_rubric(
    vacancy_id: UUID,
    rubric_id: UUID,
    body: RubricUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> RubricResponse:
    await get_agency_vacancy(db, vacancy_id, current_user.agency_id)
    result = await db.execute(
        select(VacancyRubric).where(
            VacancyRubric.id == rubric_id,
            VacancyRubric.vacancy_id == vacancy_id,
        )
    )
    rubric = result.scalar_one_or_none()
    if rubric is None:
        raise HTTPException(status_code=404, detail="Rubric not found")
    rubric = await rubric_service.update_draft_rubric(
        db,
        rubric=rubric,
        rubric_json=body.rubric_json.model_dump(),
    )
    return _rubric_to_response(rubric)


@router.post("/{vacancy_id}/rubric/{rubric_id}/approve", response_model=RubricResponse)
async def approve_vacancy_rubric(
    vacancy_id: UUID,
    rubric_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> RubricResponse:
    await get_agency_vacancy(db, vacancy_id, current_user.agency_id)
    result = await db.execute(
        select(VacancyRubric).where(
            VacancyRubric.id == rubric_id,
            VacancyRubric.vacancy_id == vacancy_id,
        )
    )
    rubric = result.scalar_one_or_none()
    if rubric is None:
        raise HTTPException(status_code=404, detail="Rubric not found")
    rubric = await rubric_service.approve_rubric(
        db, rubric=rubric, user=current_user
    )
    return _rubric_to_response(rubric)
