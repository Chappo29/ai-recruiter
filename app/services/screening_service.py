import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Candidate, Screening, User, Vacancy
from app.services.llm_service import run_screening
from app.utils.json_fields import dump_json_text, parse_json_text

logger = logging.getLogger(__name__)

_DIALOG_LOG_KEYS = (
    "strengths",
    "weaknesses",
    "red_flags",
    "verification_questions",
)


def _build_dialog_log(llm_result: dict) -> dict | None:
    payload = {key: llm_result[key] for key in _DIALOG_LOG_KEYS if key in llm_result}
    return payload or None


def merge_bot_dialog(existing: str | dict | list | None, messages: list[dict]) -> list[dict]:
    base = parse_json_text(existing)
    if base is None:
        dialog: list[dict] = []
    elif isinstance(base, list):
        dialog = list(base)
    elif isinstance(base, dict) and "messages" in base:
        dialog = list(base.get("messages") or [])
    else:
        dialog = [{"legacy": base}]
    dialog.extend(messages)
    return dialog


async def get_user_vacancy(
    db: AsyncSession, vacancy_id: UUID, user: User
) -> Vacancy:
    result = await db.execute(
        select(Vacancy).where(Vacancy.id == vacancy_id, Vacancy.user_id == user.id)
    )
    vacancy = result.scalar_one_or_none()
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")
    return vacancy


async def create_pending_screening(
    db: AsyncSession,
    *,
    vacancy_id: UUID,
    candidate_id: UUID,
) -> Screening:
    result = await db.execute(select(Vacancy).where(Vacancy.id == vacancy_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")

    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    screening = Screening(
        vacancy_id=vacancy_id,
        candidate_id=candidate_id,
        status="pending",
    )
    db.add(screening)
    await db.commit()
    await db.refresh(screening)
    return screening


async def complete_screening(db: AsyncSession, screening_id: UUID) -> Screening:
    result = await db.execute(
        select(Screening)
        .options(joinedload(Screening.candidate), joinedload(Screening.vacancy))
        .where(Screening.id == screening_id)
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")

    vacancy = screening.vacancy
    candidate = screening.candidate

    if vacancy is None or candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening data not found")

    vacancy_text = "\n\n".join(
        part
        for part in (vacancy.title, vacancy.requirements, vacancy.description)
        if part
    )
    if vacancy.ai_screening_prompt:
        vacancy_text = f"{vacancy_text}\n\nВводные рекрутера:\n{vacancy.ai_screening_prompt}"

    resume_text = candidate.resume_text
    if not resume_text or not resume_text.strip():
        screening.summary = "Не удалось извлечь текст резюме для анализа."
        screening.score = 0
        await db.commit()
        await db.refresh(screening)
        return screening

    try:
        llm_result = await run_screening(vacancy_text, resume_text)
        score = llm_result.get("score")
        if score is not None:
            score = int(max(0, min(100, int(score))))
        else:
            score = 0

        screening.verdict = llm_result.get("verdict")
        screening.score = score
        screening.summary = llm_result.get("summary")
        screening.ai_markers = dump_json_text(llm_result.get("ai_markers"))
        ai_dialog = _build_dialog_log(llm_result)
        if ai_dialog:
            screening.dialog_log = dump_json_text(
                merge_bot_dialog(screening.dialog_log, [{"role": "ai_analysis", "content": ai_dialog}])
            )
    except Exception:
        logger.exception("Screening LLM failed for %s", screening_id)
        screening.summary = "Ошибка анализа резюме (ИИ недоступен или вернул неверный ответ)."
        if screening.score is None:
            screening.score = 0

    await db.commit()
    await db.refresh(screening)
    return screening


async def append_dialog_messages(
    db: AsyncSession,
    screening_id: UUID,
    messages: list[dict],
) -> Screening:
    result = await db.execute(select(Screening).where(Screening.id == screening_id))
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")

    dialog = merge_bot_dialog(screening.dialog_log, messages)
    screening.dialog_log = dump_json_text(dialog)
    await db.commit()
    await db.refresh(screening)
    return screening


async def run_and_save_screening(
    db: AsyncSession,
    *,
    vacancy_id: UUID,
    candidate_id: UUID,
    user: User | None = None,
) -> Screening:
    if user is not None:
        await get_user_vacancy(db, vacancy_id, user)

    screening = await create_pending_screening(
        db, vacancy_id=vacancy_id, candidate_id=candidate_id
    )
    return await complete_screening(db, screening.id)
