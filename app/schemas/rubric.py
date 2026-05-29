"""Pydantic schemas for vacancy rubrics."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RubricCompetencySchema(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    weight: float = Field(ge=0.0, le=1.0, default=0.2)
    must_have: bool = False
    levels: dict[str, str] = Field(default_factory=dict)


class RubricJsonBody(BaseModel):
    competencies: list[RubricCompetencySchema] = Field(default_factory=list, min_length=1)
    generated_from: dict[str, Any] = Field(default_factory=dict)

    @field_validator("competencies")
    @classmethod
    def validate_competency_count(cls, value: list[RubricCompetencySchema]) -> list:
        if len(value) > 8:
            raise ValueError("rubric may contain at most 8 competencies")
        return value


class RubricUpdateRequest(BaseModel):
    rubric_json: RubricJsonBody


class RubricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vacancy_id: UUID
    version: int
    status: str
    rubric_json: dict[str, Any]
    created_by: UUID | None = None
    approved_by: UUID | None = None
    created_at: datetime
    approved_at: datetime | None = None


class RubricOverviewResponse(BaseModel):
    """Latest draft (if any) and currently approved rubric."""

    draft: RubricResponse | None = None
    approved: RubricResponse | None = None


class InterviewQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vacancy_id: UUID
    rubric_id: UUID | None = None
    competency_id: str | None = None
    question_text: str
    sort_order: int
    required: bool
    source: str
