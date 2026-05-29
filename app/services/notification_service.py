"""In-app notification service with SSE fan-out."""

import asyncio
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification

# SSE queues per user: user_id → list of asyncio.Queue
_streams: dict[uuid.UUID, list[asyncio.Queue]] = {}


async def create_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: str,
    title: str,
    message: str,
    action_url: str | None = None,
    meta: dict | None = None,
) -> Notification:
    n = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        action_url=action_url,
        meta=json.dumps(meta) if meta else None,
    )
    db.add(n)
    await db.commit()
    await db.refresh(n)

    payload: dict = {
        "notification": {
            "id": str(n.id),
            "type": n.type,
            "title": n.title,
            "message": n.message,
            "action_url": n.action_url,
            "created_at": n.created_at.isoformat(),
            "read_at": None,
        }
    }
    for q in list(_streams.get(user_id, [])):
        try:
            await q.put(payload)
        except Exception:
            pass
    return n


async def get_notifications(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 30
) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
    )
    return result.scalar_one() or 0


async def mark_read(
    db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID
) -> None:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    n = result.scalar_one_or_none()
    if n and n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        await db.commit()


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> None:
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
    )
    rows = result.scalars().all()
    if not rows:
        return
    now = datetime.now(timezone.utc)
    for n in rows:
        n.read_at = now
    await db.commit()


def subscribe(user_id: uuid.UUID) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _streams.setdefault(user_id, []).append(q)
    return q


def unsubscribe(user_id: uuid.UUID, q: asyncio.Queue) -> None:
    queues = _streams.get(user_id, [])
    if q in queues:
        queues.remove(q)
