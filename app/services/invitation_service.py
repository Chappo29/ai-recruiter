"""Persistent team invitations (replaces in-memory storage)."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import UserRole
from app.models import TeamInvitation, User


def hash_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def validate_invite_role(role: str) -> str:
    try:
        return UserRole(role).value
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Allowed: {[r.value for r in UserRole]}",
        ) from exc


async def create_invitation(
    db: AsyncSession,
    *,
    agency_id: UUID,
    email: str,
    role: str,
    invited_by: UUID,
    expires_hours: int = 24,
) -> tuple[str, TeamInvitation]:
    role = validate_invite_role(role)
    token = secrets.token_urlsafe(32)
    token_hash = hash_invitation_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

    invitation = TeamInvitation(
        agency_id=agency_id,
        email=email.lower().strip(),
        role=role,
        token_hash=token_hash,
        invited_by=invited_by,
        expires_at=expires_at,
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)
    return token, invitation


async def get_invitation_by_token(
    db: AsyncSession, token: str
) -> TeamInvitation | None:
    token_hash = hash_invitation_token(token)
    result = await db.execute(
        select(TeamInvitation).where(TeamInvitation.token_hash == token_hash)
    )
    return result.scalar_one_or_none()


async def list_pending_invitations(
    db: AsyncSession, agency_id: UUID
) -> list[TeamInvitation]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(TeamInvitation)
        .where(
            TeamInvitation.agency_id == agency_id,
            TeamInvitation.expires_at > now,
            TeamInvitation.used_at.is_(None),
        )
        .order_by(TeamInvitation.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_expired_invitations(db: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        delete(TeamInvitation).where(
            (TeamInvitation.expires_at <= now) | TeamInvitation.used_at.isnot(None)
        )
    )
    await db.commit()
