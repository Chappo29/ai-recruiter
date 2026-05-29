"""Shared internal API key verification."""

import secrets

from fastapi import HTTPException, status

from app.core.config import get_internal_api_key


def verify_internal_key(provided: str) -> None:
    expected = get_internal_api_key()
    if not secrets.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
