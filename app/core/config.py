import os


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value or not value.strip():
        raise RuntimeError(f"{name} environment variable is required")
    return value.strip()


SECRET_KEY = os.getenv("SECRET_KEY")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

DEFAULT_ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]


def get_allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    if not raw:
        return list(DEFAULT_ALLOWED_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def validate_required_secrets() -> None:
    """Raise at startup if required secrets are missing."""
    _require_env("SECRET_KEY")
    _require_env("INTERNAL_API_KEY")


def get_secret_key() -> str:
    return _require_env("SECRET_KEY")


def get_internal_api_key() -> str:
    return _require_env("INTERNAL_API_KEY")
