from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.auth import create_access_token, get_password_hash, verify_password
from app.deps import CurrentUser, DbSession
from app.models import Agency, User
from app.schemas.auth import AuthMeResponse, LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: DbSession) -> User:
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    agency = Agency(name=body.agency_name)
    db.add(agency)
    await db.flush()

    user = User(
        agency_id=agency.id,
        email=body.email,
        password_hash=get_password_hash(body.password),
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(user.id)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=AuthMeResponse)
async def me(current_user: CurrentUser) -> User:
    return current_user
