from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

VacancyStatus = Literal["active", "closed", "archived"]


class VacancyBase(BaseModel):
    title: str = Field(..., max_length=255)
    company: str = Field(..., max_length=255)
    hh_url: str | None = Field(default=None, max_length=512)
    requirements: str | None = None
    description: str | None = None
    ai_screening_prompt: str | None = None
    status: str = Field(default="active", max_length=32)


class VacancyCreate(BaseModel):
    title: str = Field(..., max_length=255)
    company: str = Field(..., max_length=255)
    hh_url: str | None = Field(default=None, max_length=512)
    requirements: str | None = None
    description: str | None = None
    ai_screening_prompt: str | None = None


class VacancyUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    hh_url: str | None = Field(default=None, max_length=512)
    requirements: str | None = None
    description: str | None = None
    ai_screening_prompt: str | None = None
    status: str | None = Field(default=None, max_length=32)


class VacancyStatusUpdate(BaseModel):
    status: str = Field(..., max_length=32)


class VacancyResponse(VacancyBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    archived_at: datetime | None = None
    created_at: datetime


class VacancyStatsResponse(BaseModel):
    pending: int = 0
    forwarded: int = 0
    rejected: int = 0
    total: int = 0


class ParseHHRequest(BaseModel):
    hh_url: HttpUrl | str


class ParseVacancyHHResponse(BaseModel):
    title: str | None = None
    requirements: str | None = None
    description: str | None = None
    company: str | None = None
    salary: str | None = None


class InternalVacancyItem(BaseModel):
    id: UUID
    title: str
    company: str
    requirements: str | None = None
    description: str | None = None
    ai_screening_prompt: str | None = None


class InternalVacancyListResponse(BaseModel):
    feedback_days: int
    vacancies: list[InternalVacancyItem]
