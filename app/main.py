"""

AI Recruiter API



Run from project root:

    uvicorn app.main:app --reload



Environment:

    DATABASE_URL  — async PostgreSQL URL (see .env.example)

    SECRET_KEY, INTERNAL_API_KEY — required (see .env.example)

"""



import asyncio
import logging

import os

from contextlib import asynccontextmanager

from pathlib import Path

from app.core.load_env import load_project_env

load_project_env()

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles

from sqlalchemy import select



from app.core.config import get_allowed_origins, validate_required_secrets

from app.database import async_session_factory, engine

from app.models import Agency

from app.routers import auth, bots, candidates, questions, screenings, vacancies

from app.routers.reminders import internal_router as reminders_internal_router

from app.scheduler import start_scheduler, stop_scheduler

from bot import manager as bot_manager



logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")





async def _autostart_bots() -> None:

    async with async_session_factory() as db:

        result = await db.execute(

            select(Agency).where(Agency.telegram_bot_token.isnot(None))

        )

        agencies = list(result.scalars().all())



    for agency in agencies:

        token = (agency.telegram_bot_token or "").strip()

        if not token:

            continue

        agency_id = str(agency.id)

        try:

            await bot_manager.start_bot(agency_id, token, BACKEND_URL)

            logger.info("Bot auto-started for agency %s", agency_id)

        except Exception:

            logger.exception("Failed to auto-start bot for agency %s", agency_id)





@asynccontextmanager

async def lifespan(app: FastAPI):

    validate_required_secrets()

    # Do not block HTTP startup on Telegram bot polling
    asyncio.create_task(_autostart_bots())

    start_scheduler()

    yield

    stop_scheduler()

    for agency_id in list(bot_manager.running_bots.keys()):

        try:

            await bot_manager.stop_bot(agency_id)

        except Exception:

            logger.exception("Failed to stop bot for agency %s on shutdown", agency_id)

    await engine.dispose()





app = FastAPI(

    title="AI Recruiter",

    description="Recruiter platform API with HH parsing and AI screening stubs",

    version="0.1.0",

    lifespan=lifespan,

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

app.include_router(screenings.router)

app.include_router(screenings.internal_router)

app.include_router(questions.router)

app.include_router(questions.internal_router)

app.include_router(reminders_internal_router)



MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"

(MEDIA_DIR / "resumes").mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")





@app.get("/health")

async def health() -> dict[str, str]:

    return {"status": "ok"}

