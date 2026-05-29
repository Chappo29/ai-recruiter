import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from jose import JWTError

from app.core.auth import decode_token
from app.core.config import AUTH_COOKIE_NAME
from app.deps import CurrentUser, DbSession
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/")
async def list_notifications(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = 30,
) -> list[dict]:
    items = await notification_service.get_notifications(db, current_user.id, limit)
    return [
        {
            "id": str(n.id),
            "type": n.type,
            "title": n.title,
            "message": n.message,
            "action_url": n.action_url,
            "created_at": n.created_at.isoformat(),
            "read_at": n.read_at.isoformat() if n.read_at else None,
        }
        for n in items
    ]


@router.get("/unread-count")
async def unread_count(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    count = await notification_service.get_unread_count(db, current_user.id)
    return {"count": count}


@router.post("/read-all")
async def mark_all_read(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    await notification_service.mark_all_read(db, current_user.id)
    return {"status": "ok"}


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    await notification_service.mark_read(db, current_user.id, notification_id)
    return {"status": "ok"}


@router.get("/stream")
async def notification_stream(request: Request) -> StreamingResponse:
    # Decode JWT from cookie or Bearer header directly — avoids holding a DB
    # session open for the entire lifetime of the SSE connection.
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        user_id = decode_token(token)
    except (JWTError, Exception):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    q = notification_service.subscribe(user_id)

    async def generator():
        from app.database import async_session_factory

        try:
            async with async_session_factory() as db:
                count = await notification_service.get_unread_count(db, user_id)
            yield f"data: {json.dumps({'unread_count': count})}\n\n"

            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    # keepalive ping — also lets the ASGI layer detect disconnect
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            # Client disconnected — uvicorn cancels the generator
            pass
        finally:
            notification_service.unsubscribe(user_id, q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
