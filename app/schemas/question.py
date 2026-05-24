from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuestionCreate(BaseModel):
    vacancy_id: UUID
    text: str = Field(..., min_length=1)
    order_index: int = 0


class QuestionUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1)
    order_index: int | None = None


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vacancy_id: UUID
    text: str
    order_index: int
    created_at: datetime


class AISuggestRequest(BaseModel):
    vacancy_id: UUID


class AISuggestResponse(BaseModel):
    questions: list[str]


class AnswerCreate(BaseModel):
    screening_id: UUID
    question_id: UUID
    answer_text: str | None = None


class AnswerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    screening_id: UUID
    question_id: UUID
    question_text: str | None = None
    answer_text: str | None
    created_at: datetime
