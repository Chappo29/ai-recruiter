from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.rbac import UserRole


class UserBase(BaseModel):
    email: EmailStr
    role: str = Field(default=UserRole.RECRUITER.value, max_length=32)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        try:
            UserRole(v)
            return v
        except ValueError:
            allowed = ", ".join(r.value for r in UserRole)
            raise ValueError(f"Role must be one of: {allowed}") from None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    role: str | None = Field(default=None, max_length=32)
    password: str | None = Field(default=None, min_length=8)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)


class UserProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agency_id: UUID
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None
    created_at: datetime
