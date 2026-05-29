"""Team management schemas."""

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.rbac import UserRole


class InviteUserRequest(BaseModel):
    """Request to invite a new user to the agency."""

    email: EmailStr
    role: str = Field(default=UserRole.RECRUITER.value, max_length=32)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        try:
            return UserRole(value).value
        except ValueError as exc:
            raise ValueError(
                f"role must be one of: {[r.value for r in UserRole]}"
            ) from exc
    
    
class InviteUserResponse(BaseModel):
    """Response with invitation token."""
    invitation_token: str
    expires_in_hours: int = 24


class AcceptInviteRequest(BaseModel):
    """Request to accept invitation."""
    invitation_token: str
    password: str = Field(..., min_length=8)
