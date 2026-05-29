import os


def _require_env(name: str, min_length: int = 0) -> str:
    """Get required environment variable with optional length validation."""
    value = os.getenv(name)
    if not value or not value.strip():
        raise RuntimeError(f"{name} environment variable is required")
    value = value.strip()
    if min_length > 0 and len(value) < min_length:
        raise RuntimeError(
            f"{name} must be at least {min_length} characters "
            f"(got {len(value)}). Use: openssl rand -hex 32"
        )
    return value


SECRET_KEY = os.getenv("SECRET_KEY")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

DEFAULT_ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]


# File upload limits
MAX_RESUME_SIZE_MB = int(os.getenv("MAX_RESUME_SIZE_MB", "10"))
MAX_AVATAR_SIZE_MB = int(os.getenv("MAX_AVATAR_SIZE_MB", "5"))
MAX_RESUME_SIZE_BYTES = MAX_RESUME_SIZE_MB * 1024 * 1024
MAX_AVATAR_SIZE_BYTES = MAX_AVATAR_SIZE_MB * 1024 * 1024


# LLM settings
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
OLLAMA_TIMEOUT_SEC = int(os.getenv("OLLAMA_TIMEOUT_SEC", "300"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0"))
OLLAMA_TOP_P = float(os.getenv("OLLAMA_TOP_P", "0.9"))
_seed_raw = os.getenv("OLLAMA_SEED", "").strip()
OLLAMA_SEED = int(_seed_raw) if _seed_raw.isdigit() else None
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_PROMPT_VERSION = os.getenv("LLM_PROMPT_VERSION", "v1-hardening")

# Score thresholds (code-computed verdict/bucket; no auto-reject)
SCORE_FIT_MIN = int(os.getenv("SCORE_FIT_MIN", "75"))
SCORE_MAYBE_MIN = int(os.getenv("SCORE_MAYBE_MIN", "50"))
SCORE_RECOMMENDED_MIN = int(os.getenv("SCORE_RECOMMENDED_MIN", "75"))

# Screening pipeline flags (PR #3+; off by default for PR #1)
SCREENING_RUBRIC_PIPELINE = os.getenv(
    "SCREENING_RUBRIC_PIPELINE", "false"
).strip().lower() in ("1", "true", "yes")
SCREENING_SHADOW_MODE = os.getenv("SCREENING_SHADOW_MODE", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)
STRUCTURED_INTERVIEW = os.getenv("STRUCTURED_INTERVIEW", "false").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)


# Backend URLs
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BOT_WORKER_URL = os.getenv("BOT_WORKER_URL", "http://127.0.0.1:8001")


# Default values
DEFAULT_FEEDBACK_DAYS = int(os.getenv("DEFAULT_FEEDBACK_DAYS", "3"))

# Telegram bot rate limit (seconds between messages from same user)
BOT_RATE_LIMIT_SEC = float(os.getenv("BOT_RATE_LIMIT_SEC", "1.0"))

# PDF parsing safety
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "30"))

# Auth cookie
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "access_token")
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)
AUTH_COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "lax")

# Public self-service registration
REGISTRATION_ENABLED = os.getenv("REGISTRATION_ENABLED", "true").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)

# Rate limits (additional)
RATE_LIMIT_TEAM = os.getenv("RATE_LIMIT_TEAM", "30/minute")
RATE_LIMIT_SCREENINGS = os.getenv("RATE_LIMIT_SCREENINGS", "60/minute")
RATE_LIMIT_PARSE_HH = os.getenv("RATE_LIMIT_PARSE_HH", "20/minute")


def get_allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    if not raw:
        return list(DEFAULT_ALLOWED_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def validate_required_secrets() -> None:
    """Raise at startup if required secrets are missing or too weak."""
    _require_env("SECRET_KEY", min_length=32)
    _require_env("INTERNAL_API_KEY", min_length=32)


def get_secret_key() -> str:
    return _require_env("SECRET_KEY", min_length=32)


def get_internal_api_key() -> str:
    return _require_env("INTERNAL_API_KEY", min_length=32)
