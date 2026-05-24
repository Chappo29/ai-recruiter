"""Persist bot-worker runtime state (readable from any API worker)."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotRuntime

HEARTBEAT_TTL = timedelta(seconds=90)


async def upsert_runtime(
    db: AsyncSession,
    agency_id: UUID | str,
    *,
    status: str,
    bot_username: str | None = None,
    heartbeat: bool = False,
) -> None:
    aid = agency_id if isinstance(agency_id, UUID) else UUID(str(agency_id))
    now = datetime.now(tz=timezone.utc)
    result = await db.execute(select(BotRuntime).where(BotRuntime.agency_id == aid))
    row = result.scalar_one_or_none()
    if row is None:
        row = BotRuntime(
            agency_id=aid,
            status=status,
            bot_username=bot_username,
            last_heartbeat_at=now if heartbeat else None,
        )
        db.add(row)
    else:
        row.status = status
        if bot_username is not None:
            row.bot_username = bot_username
        if heartbeat:
            row.last_heartbeat_at = now
    await db.commit()


async def mark_stopped(db: AsyncSession, agency_id: UUID | str) -> None:
    await upsert_runtime(db, agency_id, status="stopped", bot_username=None, heartbeat=False)


async def is_runtime_alive(db: AsyncSession, agency_id: UUID | str) -> bool:
    aid = agency_id if isinstance(agency_id, UUID) else UUID(str(agency_id))
    result = await db.execute(select(BotRuntime).where(BotRuntime.agency_id == aid))
    row = result.scalar_one_or_none()
    if row is None or row.status != "running":
        return False
    if row.last_heartbeat_at is None:
        return False
    hb = row.last_heartbeat_at
    if hb.tzinfo is None:
        hb = hb.replace(tzinfo=timezone.utc)
    return datetime.now(tz=timezone.utc) - hb < HEARTBEAT_TTL


async def get_runtime(
    db: AsyncSession, agency_id: UUID | str
) -> BotRuntime | None:
    aid = agency_id if isinstance(agency_id, UUID) else UUID(str(agency_id))
    result = await db.execute(select(BotRuntime).where(BotRuntime.agency_id == aid))
    return result.scalar_one_or_none()
