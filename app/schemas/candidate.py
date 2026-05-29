from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class CandidateBase(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    telegram_id: str | None = Field(default=None, max_length=64)
    hh_url: str | None = Field(default=None, max_length=512)
    resume_text: str | None = None


class CandidateCreate(CandidateBase):
    pass


class CandidateUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    telegram_id: str | None = Field(default=None, max_length=64)
    hh_url: str | None = Field(default=None, max_length=512)
    resume_text: str | None = None


class CandidateResponse(CandidateBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str | None = None
    resume_file_path: str | None = None
    avatar_file_path: str | None = None
    created_at: datetime


class ParseHHRequest(BaseModel):
    hh_url: HttpUrl | str


class ResumeUploadRequest(BaseModel):
    candidate_id: UUID
    agency_id: UUID
    file_base64: str
    filename: str = "resume.pdf"


class ResumeUploadResponse(BaseModel):
    file_path: str


class CandidateUploadAvatarRequest(BaseModel):
    candidate_id: UUID
    agency_id: UUID
    file_base64: str
    filename: str = "avatar.jpg"


class CandidateUploadAvatarResponse(BaseModel):
    status: str = "ok"
    avatar_file_path: str


class ParseResumeHHResponse(BaseModel):
    full_name: str | None = None
    title: str | None = None
    experience: str | None = None
    skills: str | None = None
    resume_text: str | None = None
