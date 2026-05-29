"""Role-Based Access Control (RBAC) module."""

from enum import Enum
from functools import wraps
from typing import Callable

from fastapi import HTTPException, status

from app.models import User


class UserRole(str, Enum):
    """User roles with hierarchy: admin > recruiter."""
    
    ADMIN = "admin"
    RECRUITER = "recruiter"


# Role hierarchy (lower number = higher privileges)
ROLE_HIERARCHY = {
    UserRole.ADMIN: 1,
    UserRole.RECRUITER: 2,
}


def get_role_level(role: str) -> int:
    """Get numeric level for role (lower = more privileges)."""
    try:
        return ROLE_HIERARCHY[UserRole(role)]
    except (ValueError, KeyError):
        return 999  # Unknown roles have lowest privileges


def has_role(user: User, required_role: UserRole) -> bool:
    """Check if user has required role or higher."""
    user_level = get_role_level(user.role)
    required_level = ROLE_HIERARCHY[required_role]
    return user_level <= required_level


def require_role(required_role: UserRole) -> Callable:
    """
    Decorator to require specific role for endpoint.
    
    Usage:
        @router.get("/admin-only")
        @require_role(UserRole.ADMIN)
        async def admin_endpoint(current_user: CurrentUser):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find current_user in kwargs (injected by FastAPI)
            current_user = kwargs.get("current_user")
            if current_user is None:
                # Try to find in args (less common)
                for arg in args:
                    if isinstance(arg, User):
                        current_user = arg
                        break
            
            if current_user is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Authentication required but user not found",
                )
            
            if not has_role(current_user, required_role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Требуется роль '{required_role.value}' или выше",
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def is_admin(user: User) -> bool:
    """Check if user is admin."""
    return has_role(user, UserRole.ADMIN)


def is_recruiter_or_above(user: User) -> bool:
    """Check if user is recruiter or admin."""
    return has_role(user, UserRole.RECRUITER)
