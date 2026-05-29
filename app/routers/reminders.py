"""Internal API endpoints for candidate reminder management."""

import uuid
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, update as sa_update

from app.core.internal_auth import verify_internal_key
from app.core.rate_limit import internal_limit
from app.database import async_session_factory
from app.models import CandidateReminder

internal_router = APIRouter(prefix="/internal", tags=["internal"])


class ReminderCreate(BaseModel):
    telegram_id: str
    agency_id: str
    state: str  # "waiting_resume" | "waiting_answers"
    vacancy_title: str
    screening_id: Optional[str] = None


class ReminderCancel(BaseModel):
    telegram_id: str
    agency_id: str


class ReminderResponse(BaseModel):
    id: str
    telegram_id: str
    agency_id: str
    state: str
    vacancy_title: str
    screening_id: Optional[str]
    cancelled: bool


@internal_router.post(
    "/reminders/",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
)
@internal_limit()
async def create_reminder(
    request: Request,
    body: ReminderCreate,
    x_internal_key: str = Header(...),
) -> ReminderResponse:
    verify_internal_key(x_internal_key)

    async with async_session_factory() as db:
        reminder = CandidateReminder(
            telegram_id=body.telegram_id,
            agency_id=body.agency_id,
            state=body.state,
            vacancy_title=body.vacancy_title,
            screening_id=uuid.UUID(body.screening_id) if body.screening_id else None,
        )
        db.add(reminder)
        await db.commit()
        await db.refresh(reminder)

    return ReminderResponse(
        id=str(reminder.id),
        telegram_id=reminder.telegram_id,
        agency_id=reminder.agency_id,
        state=reminder.state,
        vacancy_title=reminder.vacancy_title,
        screening_id=str(reminder.screening_id) if reminder.screening_id else None,
        cancelled=reminder.cancelled,
    )


@internal_router.post("/reminders/cancel", status_code=status.HTTP_200_OK)
@internal_limit()
async def cancel_reminders(
    request: Request,
    body: ReminderCancel,
    x_internal_key: str = Header(...),
) -> dict:
    verify_internal_key(x_internal_key)

    async with async_session_factory() as db:
        result = await db.execute(
            select(CandidateReminder).where(
                CandidateReminder.telegram_id == body.telegram_id,
                CandidateReminder.agency_id == body.agency_id,
                CandidateReminder.cancelled == False,  # noqa: E712
            )
        )
        reminders = result.scalars().all()
        for r in reminders:
            r.cancelled = True
        await db.commit()

    return {"cancelled": len(reminders)}
