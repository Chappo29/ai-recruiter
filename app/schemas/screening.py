from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.json_fields import parse_json_text


class ScreeningBase(BaseModel):
    vacancy_id: UUID
    candidate_id: UUID
    status: str = Field(default="pending", max_length=32)


class ScreeningCreate(BaseModel):
    vacancy_id: UUID
    candidate_id: UUID


class ScreeningUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=32)
    verdict: str | None = Field(default=None, max_length=32)
    score: int | None = None
    summary: str | None = None


class ScreeningStatusUpdate(BaseModel):
    status: str = Field(..., max_length=32)


class ScreeningStats(BaseModel):
    vacancy_id: UUID
    total: int = 0
    fit: int = 0
    maybe: int = 0
    reject: int = 0
    pending: int = 0


class AnswersEvaluationResponse(BaseModel):
    answers_summary: str | None = None
    answers_score: int | None = None
    strong_answers: list[str] = Field(default_factory=list)
    weak_answers: list[str] = Field(default_factory=list)


class ScreeningCandidateBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str | None = None
    telegram_id: str | None = None
    avatar_file_path: str | None = None


class ScreeningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vacancy_id: UUID
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
