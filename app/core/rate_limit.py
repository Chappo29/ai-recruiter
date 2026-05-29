"""HTTP rate limiting (slowapi). Disabled automatically if slowapi is not installed."""

import os

from fastapi import Request

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False

    def get_remote_address(request: Request) -> str:  # noqa: ARG001
        return "127.0.0.1"

    Limiter = None  # type: ignore[misc, assignment]

RATE_LIMIT_AUTH_LOGIN = os.getenv("RATE_LIMIT_AUTH_LOGIN", "10/minute")
RATE_LIMIT_AUTH_REGISTER = os.getenv("RATE_LIMIT_AUTH_REGISTER", "5/hour")
RATE_LIMIT_INTERNAL = os.getenv("RATE_LIMIT_INTERNAL", "120/minute")
RATE_LIMIT_HEALTH = os.getenv("RATE_LIMIT_HEALTH", "120/minute")


def rate_limit_enabled() -> bool:
    if not SLOWAPI_AVAILABLE:
        return False
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


if SLOWAPI_AVAILABLE:
    limiter = Limiter(
        key_func=get_remote_address,
        headers_enabled=False,
        storage_uri=os.getenv("RATE_LIMIT_STORAGE_URI", "memory://"),
    )
else:
    limiter = None


def _noop_decorator(func):
    return func


def auth_login_limit():
    if not rate_limit_enabled() or limiter is None:
        return _noop_decorator
    return limiter.limit(RATE_LIMIT_AUTH_LOGIN)


def auth_register_limit():
    if not rate_limit_enabled() or limiter is None:
        return _noop_decorator
    return limiter.limit(RATE_LIMIT_AUTH_REGISTER)


def internal_limit():
    if not rate_limit_enabled() or limiter is None:
        return _noop_decorator
    return limiter.shared_limit(
        RATE_LIMIT_INTERNAL,
        scope="internal_api",
        key_func=internal_key_func,
    )


def health_limit():
    if not rate_limit_enabled() or limiter is None:
        return _noop_decorator
    return limiter.limit(RATE_LIMIT_HEALTH)


def team_limit():
    if not rate_limit_enabled() or limiter is None:
        return _noop_decorator
    from app.core.config import RATE_LIMIT_TEAM

    return limiter.limit(RATE_LIMIT_TEAM)


def screenings_limit():
    if not rate_limit_enabled() or limiter is None:
        return _noop_decorator
    from app.core.config import RATE_LIMIT_SCREENINGS

    return limiter.limit(RATE_LIMIT_SCREENINGS)


def parse_hh_limit():
    if not rate_limit_enabled() or limiter is None:
        return _noop_decorator
    from app.core.config import RATE_LIMIT_PARSE_HH

    return limiter.limit(RATE_LIMIT_PARSE_HH)
