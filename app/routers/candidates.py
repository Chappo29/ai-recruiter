import base64
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.core.internal_auth import verify_internal_key
from app.core.rate_limit import internal_limit, parse_hh_limit
from app.deps import CurrentUser, DbSession
from app.models import Candidate, Screening, Vacancy, User
from app.schemas.candidate import (
    CandidateResponse,
    CandidateUploadAvatarRequest,
    CandidateUploadAvatarResponse,
    ParseHHRequest,
    ParseResumeHHResponse,
)
from app.services import hh_parser
from app.services.agency_access import get_agency_candidate
from app.utils.file_validation import validate_image_file

router = APIRouter(prefix="/candidates", tags=["candidates"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])

AVATAR_MEDIA_DIR = Path(__file__).resolve().parents[2] / "media" / "avatars"
RESUME_MEDIA_DIR = Path(__file__).resolve().parents[2] / "media" / "resumes"
ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _resolve_media_path(stored_path: str | None, base_dir: Path) -> Path | None:
    if not stored_path:
        return None
    name = Path(stored_path).name
    if not name or ".." in name or name.startswith("."):
        return None
    candidate_path = (base_dir / name).resolve()
    if base_dir.resolve() not in candidate_path.parents and candidate_path != base_dir.resolve():
        return None
    if not candidate_path.is_file():
        return None
    return candidate_path


@router.post("/parse-hh", response_model=ParseResumeHHResponse)
@parse_hh_limit()
async def parse_resume_hh(
    request: Request,
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
    await get_agency_candidate(db, candidate_id, current_user.agency_id)
    result = await db.execute(
        select(Candidate)
        .join(Screening, Screening.candidate_id == Candidate.id)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .join(User, Vacancy.user_id == User.id)
        .where(
            Candidate.id == candidate_id,
            User.agency_id == current_user.agency_id,
        )
        .limit(1)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidate


@router.get("/{candidate_id}/avatar")
async def download_candidate_avatar(
    candidate_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    candidate = await get_agency_candidate(db, candidate_id, current_user.agency_id)
    file_path = _resolve_media_path(candidate.avatar_file_path, AVATAR_MEDIA_DIR)
    if file_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")
    return FileResponse(file_path, media_type="image/jpeg")


@router.get("/{candidate_id}/resume")
async def download_candidate_resume(
    candidate_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    candidate = await get_agency_candidate(db, candidate_id, current_user.agency_id)
    file_path = _resolve_media_path(candidate.resume_file_path, RESUME_MEDIA_DIR)
    if file_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return FileResponse(file_path, media_type="application/pdf")


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
    verify_internal_key(x_internal_key)
    candidate = await get_agency_candidate(db, body.candidate_id, body.agency_id)

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

    validate_image_file(file_bytes)

    AVATAR_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{body.candidate_id}_{uuid.uuid4().hex[:8]}.jpg"
    file_path_rel = f"/media/avatars/{stored_name}"
    file_path_abs = AVATAR_MEDIA_DIR / stored_name

    with open(file_path_abs, "wb") as f:
        f.write(file_bytes)

    candidate.avatar_file_path = file_path_rel
    await db.commit()

    return CandidateUploadAvatarResponse(avatar_file_path=file_path_rel)
