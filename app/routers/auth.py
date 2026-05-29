import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, File, status
from sqlalchemy import select

from app.core.auth import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, get_password_hash, verify_password
from app.core.config import (
    AUTH_COOKIE_NAME,
    AUTH_COOKIE_SAMESITE,
    AUTH_COOKIE_SECURE,
    REGISTRATION_ENABLED,
)
from app.core.rate_limit import auth_login_limit, auth_register_limit
from app.core.rbac import UserRole
from app.deps import CurrentUser, DbSession
from app.models import Agency, User
from app.schemas.auth import AuthMeResponse, LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserProfileUpdate, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

AVATAR_DIR = Path(__file__).resolve().parents[2] / "media" / "user_avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5 MB


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@auth_register_limit()
async def register(request: Request, body: RegisterRequest, db: DbSession, response: Response) -> User:
    if not REGISTRATION_ENABLED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is disabled")

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to complete registration")

    agency = Agency(name=body.agency_name)
    db.add(agency)
    await db.flush()

    user = User(
        agency_id=agency.id,
        email=body.email,
        password_hash=get_password_hash(body.password),
        role=UserRole.ADMIN.value,
        first_name=body.first_name,
        last_name=body.last_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    access_token = create_access_token(user.id)
    _set_auth_cookie(response, access_token)
    return user


@router.post("/login", response_model=TokenResponse)
@auth_login_limit()
async def login(request: Request, body: LoginRequest, db: DbSession, response: Response) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    access_token = create_access_token(user.id)
    _set_auth_cookie(response, access_token)
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")


@router.get("/me", response_model=AuthMeResponse)
async def me(current_user: CurrentUser) -> User:
    return current_user


@router.patch("/me", response_model=AuthMeResponse)
async def update_me(body: UserProfileUpdate, current_user: CurrentUser, db: DbSession) -> User:
    if body.first_name is not None:
        current_user.first_name = body.first_name.strip() or None
    if body.last_name is not None:
        current_user.last_name = body.last_name.strip() or None
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/me/avatar", response_model=AuthMeResponse)
async def upload_avatar(
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
) -> User:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Допустимые форматы: JPEG, PNG, WebP")

    contents = await file.read()
    if len(contents) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="Файл слишком большой (максимум 5 МБ)")

    # Remove old avatar file
    if current_user.avatar_url:
        old_path = AVATAR_DIR / Path(current_user.avatar_url).name
        if old_path.exists():
            old_path.unlink()

    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "jpg"
    stored_name = f"{uuid.uuid4()}.{ext}"
    dest = AVATAR_DIR / stored_name
    dest.write_bytes(contents)

    current_user.avatar_url = f"/media/user_avatars/{stored_name}"
    await db.commit()
    await db.refresh(current_user)
    return current_user
