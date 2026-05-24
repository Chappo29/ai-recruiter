import base64
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.core.config import get_internal_api_key
from app.core.rate_limit import internal_limit
from app.deps import CurrentUser, DbSession
from app.models import Candidate, Screening, Vacancy
from app.schemas.candidate import (
    CandidateCreate,
    CandidateResponse,
    CandidateUploadAvatarRequest,
    CandidateUploadAvatarResponse,
    ParseHHRequest,
    ParseResumeHHResponse,
)
from app.services import hh_parser

router = APIRouter(prefix="/candidates", tags=["candidates"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])

AVATAR_MEDIA_DIR = Path(__file__).resolve().parents[2] / "media" / "avatars"
ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _check_internal_key(x_internal_key: str) -> None:
    if x_internal_key != get_internal_api_key():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


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


@internal_router.post(
    "/candidates/upload-avatar",
    response_model=CandidateUploadAvatarResponse,
)
@internal_limit()
async def upload_candidate_avatar(
    request: Request,
    body: CandidateUploadAvatarRequest,
    db: DbSession,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> CandidateUploadAvatarResponse:
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

    filename = (body.filename or "avatar.jpg").lower()
    suffix = Path(filename).suffix or ".jpg"
    if suffix not in ALLOWED_AVATAR_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, PNG or WEBP images are allowed",
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

    AVATAR_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{body.candidate_id}_{uuid.uuid4().hex[:8]}.jpg"
    file_path_rel = f"/media/avatars/{stored_name}"
    file_path_abs = AVATAR_MEDIA_DIR / stored_name

    with open(file_path_abs, "wb") as f:
        f.write(file_bytes)

    candidate.avatar_file_path = file_path_rel
    await db.commit()

    return CandidateUploadAvatarResponse(avatar_file_path=file_path_rel)
