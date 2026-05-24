"""
AI Recruiter API

Run from project root:
    uvicorn app.main:app --reload

Bot polling (separate process):
    python -m bot

Environment:
    DATABASE_URL  — async PostgreSQL URL (see .env.example)
    SECRET_KEY, INTERNAL_API_KEY — required (see .env.example)
    BOT_WORKER_URL — control API for start/stop (default http://127.0.0.1:8001)
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from app.core.load_env import load_project_env

load_project_env()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import get_allowed_origins, validate_required_secrets
from app.core.rate_limit import SLOWAPI_AVAILABLE, health_limit, limiter

if SLOWAPI_AVAILABLE:
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
else:
    RateLimitExceeded = Exception  # type: ignore[misc, assignment]
    SlowAPIMiddleware = None  # type: ignore[misc, assignment]
from app.database import engine
from app.routers import auth, bots, candidates, questions, screenings, vacancies
from app.routers.reminders import internal_router as reminders_internal_router
from app.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)
BOT_WORKER_URL = os.getenv("BOT_WORKER_URL", "http://127.0.0.1:8001")


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_required_secrets()
    # Telegram polling runs in bot-worker only (python -m bot)
    start_scheduler()
    yield
    stop_scheduler()
    await engine.dispose()


app = FastAPI(
    title="AI Recruiter",
    description="Recruiter platform API with HH parsing and AI screening stubs",
    version="0.1.0",
    lifespan=lifespan,
)
if SLOWAPI_AVAILABLE and limiter is not None:
    app.state.limiter = limiter

    async def rate_limit_exceeded_handler(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": "Слишком много запросов. Попробуйте позже."},
            headers=exc.headers,
        )

    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
else:
    logger.warning(
        "slowapi is not installed — API starts without rate limits. "
        "Prefer: .\\run-api.ps1 or .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload"
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(bots.router)
app.include_router(vacancies.router)
app.include_router(vacancies.internal_router)
app.include_router(candidates.router)
app.include_router(candidates.internal_router)
app.include_router(screenings.router)
app.include_router(screenings.internal_router)
app.include_router(questions.router)
app.include_router(questions.internal_router)
app.include_router(reminders_internal_router)

MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"
(MEDIA_DIR / "resumes").mkdir(parents=True, exist_ok=True)
(MEDIA_DIR / "avatars").mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


@app.get("/health")
@health_limit()
async def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "bot_worker_url": BOT_WORKER_URL}
