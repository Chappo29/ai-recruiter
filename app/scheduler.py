"""APScheduler-based reminder system for abandoned candidates."""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, update as sa_update

from app.database import async_session_factory
from app.models import CandidateReminder, Screening
from bot.outbound import send_message

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# ── Timing constants ──────────────────────────────────────────────────────────
_STATE_A_FIRST = timedelta(hours=4)
_STATE_B_FIRST = timedelta(hours=2)
_SECOND_REMINDER = timedelta(hours=24)
_CLOSE_AT = timedelta(hours=72)

# ── Message templates ─────────────────────────────────────────────────────────
_MSG_A_4H = (
    "Привет! 👋 Вы начали отклик на вакансию {title}. "
    "Это займёт буквально пару минут — просто пришлите PDF резюме. "
    "Будем рады рассмотреть вашу кандидатуру! 📄"
)
_MSG_A_24H = (
    "Вакансия {title} всё ещё открыта и ждёт вас 🙌 "
    "Если хотите продолжить — просто пришлите резюме PDF."
)
_MSG_B_2H = (
    "Вы уже почти всё сделали! 😊 "
    "Осталось ответить на несколько коротких вопросов по вакансии {title}. "
    "Напишите /start чтобы продолжить."
)
_MSG_B_24H = (
    "Вакансия {title} ещё открыта, рекрутер ждёт ваши ответы 🙌 "
    "Напишите /start чтобы продолжить."
)


async def _send(agency_id: str, telegram_id: str, text: str) -> bool:
    """Send a Telegram message; return True on success."""
    try:
        async with async_session_factory() as db:
            await send_message(db, agency_id, telegram_id, text)
        return True
    except RuntimeError as exc:
        logger.warning(
            "Cannot send reminder agency=%s telegram_id=%s: %s",
            agency_id,
            telegram_id,
            exc,
        )
        return False
    except Exception:
        logger.warning(
            "Failed to send reminder to telegram_id=%s (agency=%s)",
            telegram_id,
            agency_id,
            exc_info=True,
        )
        return False


async def check_reminders() -> None:
    """Scheduled job: evaluate all active reminders and send messages / close sessions."""
    now = datetime.now(tz=timezone.utc)

    async with async_session_factory() as db:
        result = await db.execute(
            select(CandidateReminder).where(CandidateReminder.cancelled == False)  # noqa: E712
        )
        reminders = result.scalars().all()

    for reminder in reminders:
        try:
            await _process_reminder(reminder, now)
        except Exception:
            logger.exception(
                "Unhandled error processing reminder id=%s", reminder.id
            )


async def _process_reminder(reminder: CandidateReminder, now: datetime) -> None:
    created = reminder.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    elapsed = now - created
    title = reminder.vacancy_title
    agency_id = reminder.agency_id
    telegram_id = reminder.telegram_id

    # ── 72h: silent close ──────────────────────────────────────────────────
    if elapsed >= _CLOSE_AT:
        async with async_session_factory() as db:
            await db.execute(
                sa_update(CandidateReminder)
                .where(CandidateReminder.id == reminder.id)
                .values(cancelled=True)
            )
            if reminder.screening_id and reminder.state == "waiting_answers":
                await db.execute(
                    sa_update(Screening)
                    .where(Screening.id == reminder.screening_id)
                    .values(status="abandoned")
                )
            await db.commit()
        logger.info(
            "Reminder id=%s closed at 72h (state=%s, telegram_id=%s)",
            reminder.id,
            reminder.state,
            telegram_id,
        )
        return

    # ── 24h reminder ──────────────────────────────────────────────────────
    if not reminder.reminded_at_24h and elapsed >= _SECOND_REMINDER:
        if reminder.state == "waiting_resume":
            text = _MSG_A_24H.format(title=title)
        else:
            text = _MSG_B_24H.format(title=title)

        sent = await _send(agency_id, telegram_id, text)
        if sent:
            async with async_session_factory() as db:
                await db.execute(
                    sa_update(CandidateReminder)
                    .where(CandidateReminder.id == reminder.id)
                    .values(reminded_at_24h=True)
                )
                await db.commit()
        return

    # ── First reminder (4h for State A, 2h for State B) ───────────────────
    if not reminder.reminded_at_first:
        threshold = _STATE_A_FIRST if reminder.state == "waiting_resume" else _STATE_B_FIRST
        if elapsed >= threshold:
            if reminder.state == "waiting_resume":
                text = _MSG_A_4H.format(title=title)
            else:
                text = _MSG_B_2H.format(title=title)

            sent = await _send(agency_id, telegram_id, text)
            if sent:
                async with async_session_factory() as db:
                    await db.execute(
                        sa_update(CandidateReminder)
                        .where(CandidateReminder.id == reminder.id)
                        .values(reminded_at_first=True)
                    )
                    await db.commit()


def start_scheduler() -> None:
    scheduler.add_job(
        check_reminders,
        trigger="interval",
        minutes=15,
        id="check_reminders",
        replace_existing=True,
        misfire_grace_time=120,
    )
    scheduler.start()
    logger.info("Reminder scheduler started (interval=15min)")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Reminder scheduler stopped")
