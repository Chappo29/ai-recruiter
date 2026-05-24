from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgencyBase(BaseModel):
    name: str = Field(..., max_length=255)
    plan: str = Field(default="free", max_length=32)


class AgencyCreate(AgencyBase):
    pass


class AgencyUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    plan: str | None = Field(default=None, max_length=32)


class AgencyResponse(AgencyBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
