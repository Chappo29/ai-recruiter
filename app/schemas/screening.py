from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.json_fields import parse_json_text

ScreeningStatus = Literal["pending", "forwarded", "rejected"]
SCREENING_STATUSES = frozenset({"pending", "forwarded", "rejected"})


class ScreeningBase(BaseModel):
    vacancy_id: UUID
    candidate_id: UUID
    status: ScreeningStatus = "pending"


class ScreeningCreate(BaseModel):
    vacancy_id: UUID
    candidate_id: UUID


class ScreeningUpdate(BaseModel):
    status: ScreeningStatus | None = None
    verdict: str | None = Field(default=None, max_length=32)
    score: int | None = None
    summary: str | None = None


class ScreeningStatusUpdate(BaseModel):
    status: ScreeningStatus

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in SCREENING_STATUSES:
            raise ValueError("status must be pending, forwarded, or rejected")
        return value


class ScreeningStats(BaseModel):
    vacancy_id: UUID
    total: int = 0
    pending: int = 0
    forwarded: int = 0
    rejected: int = 0


class ScreeningCandidateBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str | None = None
    first_name: str | None = None
    telegram_id: str | None = None
    avatar_file_path: str | None = None


class ScreeningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vacancy_id: UUID
    vacancy_title: str | None = None
    candidate_id: UUID
    candidate: ScreeningCandidateBrief | None = None
    candidate_name: str | None = None
    candidate_telegram_id: str | None = None
    resume_text: str | None = None
    resume_file_path: str | None = None
    avatar_file_path: str | None = None
    verdict: str | None = None
    display_verdict: str | None = None
    verdict_label: str | None = None
    score: int | None = None
    summary: str | None = None
    ai_markers: dict[str, Any] | None = None
    dialog_log: list[Any] | dict[str, Any] | None = None
    status: str
    screening_index: int | None = None
    created_at: datetime

    @field_validator("ai_markers", "dialog_log", mode="before")
    @classmethod
    def parse_json_columns(cls, value: Any) -> dict[str, Any] | list[Any] | None:
        parsed = parse_json_text(value)
        if parsed is not None and not isinstance(parsed, (dict, list)):
            return {"value": parsed}
        return parsed
