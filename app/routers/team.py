"""Team management router - inviting users to agency."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.auth import get_password_hash
from app.core.rate_limit import team_limit
from app.core.rbac import UserRole, require_role
from app.deps import CurrentUser, DbSession
from app.models import User
from app.schemas.team import AcceptInviteRequest, InviteUserRequest, InviteUserResponse
from app.schemas.user import UserResponse
from app.services import invitation_service

router = APIRouter(prefix="/team", tags=["team"])
logger = logging.getLogger(__name__)


class PendingInvitationResponse(BaseModel):
    id: UUID
    email: str
    role: str
    expires_at: datetime
    created_at: datetime


@router.post("/invite", response_model=InviteUserResponse)
@team_limit()
@require_role(UserRole.ADMIN)
async def invite_user(
    request: Request,
    body: InviteUserRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> InviteUserResponse:
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    token, _invitation = await invitation_service.create_invitation(
        db,
        agency_id=current_user.agency_id,
        email=body.email,
        role=body.role,
        invited_by=current_user.id,
    )

    return InviteUserResponse(
        invitation_token=token,
        expires_in_hours=24,
    )


@router.post("/accept-invite", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@team_limit()
async def accept_invite(
    request: Request,
    body: AcceptInviteRequest,
    db: DbSession,
) -> User:
    invitation = await invitation_service.get_invitation_by_token(
        db, body.invitation_token
    )
    if invitation is None or invitation.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invitation token",
        )

    if datetime.now(timezone.utc) > invitation.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation token expired",
        )

    existing = await db.execute(select(User).where(User.email == invitation.email))
    if existing.scalar_one_or_none() is not None:
        invitation.used_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        agency_id=invitation.agency_id,
        email=invitation.email,
        password_hash=get_password_hash(body.password),
        role=invitation.role,
    )
    db.add(user)
    invitation.used_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    if invitation.invited_by:
        try:
            from app.services import notification_service

            await notification_service.create_notification(
                db,
                user_id=invitation.invited_by,
                type="team_joined",
                title="Новый участник",
                message=f"{invitation.email} принял приглашение в команду",
                meta={"new_user_id": str(user.id), "email": invitation.email},
            )
        except Exception:
            logger.exception("Failed to send team_joined notification")

    return user


@router.get("/invitations", response_model=list[PendingInvitationResponse])
@team_limit()
@require_role(UserRole.ADMIN)
async def list_pending_invitations(
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
) -> list[PendingInvitationResponse]:
    rows = await invitation_service.list_pending_invitations(
        db, current_user.agency_id
    )
    return [
        PendingInvitationResponse(
            id=row.id,
            email=row.email,
            role=row.role,
            expires_at=row.expires_at,
            created_at=row.created_at,
        )
        for row in rows
    ]
