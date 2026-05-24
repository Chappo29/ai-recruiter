"""HTTP rate limiting (slowapi)."""

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

RATE_LIMIT_AUTH_LOGIN = os.getenv("RATE_LIMIT_AUTH_LOGIN", "10/minute")
RATE_LIMIT_AUTH_REGISTER = os.getenv("RATE_LIMIT_AUTH_REGISTER", "5/hour")
RATE_LIMIT_INTERNAL = os.getenv("RATE_LIMIT_INTERNAL", "120/minute")
RATE_LIMIT_HEALTH = os.getenv("RATE_LIMIT_HEALTH", "120/minute")


def rate_limit_enabled() -> bool:
    return os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def internal_key_func(request: Request) -> str:
    remote = get_remote_address(request)
    key_prefix = (request.headers.get("X-Internal-Key") or "")[:12]
    return f"{remote}:{key_prefix}"


limiter = Limiter(
    key_func=get_remote_address,
    headers_enabled=True,
    storage_uri=os.getenv("RATE_LIMIT_STORAGE_URI", "memory://"),
)


def _noop_decorator(func):
    return func


def auth_login_limit():
    if not rate_limit_enabled():
        return _noop_decorator
    return limiter.limit(RATE_LIMIT_AUTH_LOGIN)


def auth_register_limit():
    if not rate_limit_enabled():
        return _noop_decorator
    return limiter.limit(RATE_LIMIT_AUTH_REGISTER)


def internal_limit():
    if not rate_limit_enabled():
        return _noop_decorator
    return limiter.shared_limit(
        RATE_LIMIT_INTERNAL,
        scope="internal_api",
        key_func=internal_key_func,
    )


def health_limit():
    if not rate_limit_enabled():
        return _noop_decorator
    return limiter.limit(RATE_LIMIT_HEALTH)
