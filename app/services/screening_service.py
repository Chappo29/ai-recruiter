import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import joinedload

from app.models import Candidate, CandidateAnswer, Screening, User, Vacancy
from app.services.llm_service import evaluate_interview_answers, run_screening
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


def _merge_answers_evaluation_into_dialog_log(
    existing: str | dict | list | None, evaluation: dict
) -> dict:
    base = parse_json_text(existing)
    if base is None:
        dialog: dict = {}
    elif isinstance(base, dict):
        dialog = dict(base)
    else:
        dialog = {"legacy": base}

    dialog["answers_summary"] = evaluation.get("answers_summary")
    dialog["answers_score"] = evaluation.get("answers_score")
    dialog["strong_answers"] = evaluation.get("strong_answers") or []
    dialog["weak_answers"] = evaluation.get("weak_answers") or []
    return dialog


def _format_qa_pairs(answers: list[CandidateAnswer]) -> str:
    lines: list[str] = []
    for index, answer in enumerate(answers, start=1):
        question_text = (
            answer.question.text if answer.question else f"Вопрос {index}"
        )
        answer_text = answer.answer_text or "(нет ответа)"
        lines.append(f"Вопрос: {question_text}\nОтвет: {answer_text}")
    return "\n\n".join(lines)


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
    result = await db.execute(select(Screening).where(Screening.id == screening_id))
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")

    vacancy_result = await db.execute(
        select(Vacancy).where(Vacancy.id == screening.vacancy_id)
    )
    vacancy = vacancy_result.scalar_one_or_none()
    candidate_result = await db.execute(
        select(Candidate).where(Candidate.id == screening.candidate_id)
    )
    candidate = candidate_result.scalar_one_or_none()

    if vacancy is None or candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening data not found")

    vacancy_text = "\n\n".join(
        part
        for part in (vacancy.title, vacancy.requirements, vacancy.description)
        if part
    )
    resume_text = candidate.resume_text
    if not resume_text or not resume_text.strip():
        screening.status = "failed"
        await db.commit()
        await db.refresh(screening)
        return screening

    try:
        llm_result = await run_screening(vacancy_text, resume_text)
        score = llm_result.get("score")
        if score is not None:
            score = int(score)

        screening.verdict = llm_result.get("verdict")
        screening.score = score
        screening.summary = llm_result.get("summary")
        screening.ai_markers = dump_json_text(llm_result.get("ai_markers"))
        screening.dialog_log = dump_json_text(_build_dialog_log(llm_result))
        screening.status = "completed"
    except Exception:
        logger.exception("Screening %s failed", screening_id)
        screening.status = "failed"
        await db.commit()
        await db.refresh(screening)
        return screening

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
        vacancy = await get_user_vacancy(db, vacancy_id, user)
    else:
        result = await db.execute(select(Vacancy).where(Vacancy.id == vacancy_id))
        vacancy = result.scalar_one_or_none()
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vacancy not found",
            )

    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    vacancy_text = "\n\n".join(
        part
        for part in (
            vacancy.title,
            vacancy.requirements,
            vacancy.description,
        )
        if part
    )

    resume_text = candidate.resume_text
    if not resume_text or not resume_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidate resume text is empty",
        )

    llm_result = await run_screening(vacancy_text, resume_text)

    score = llm_result.get("score")
    if score is not None:
        score = int(score)

    screening = Screening(
        vacancy_id=vacancy.id,
        candidate_id=candidate.id,
        verdict=llm_result.get("verdict"),
        score=score,
        summary=llm_result.get("summary"),
        ai_markers=dump_json_text(llm_result.get("ai_markers")),
        dialog_log=dump_json_text(_build_dialog_log(llm_result)),
        status="completed",
    )
    db.add(screening)
    await db.commit()
    await db.refresh(screening)
    return screening


async def evaluate_screening_answers(
    db: AsyncSession,
    screening_id: UUID,
    user: User,
) -> tuple[Screening, dict]:
    result = await db.execute(
        select(Screening)
        .join(Vacancy, Screening.vacancy_id == Vacancy.id)
        .options(joinedload(Screening.candidate))
        .where(
            Screening.id == screening_id,
            Vacancy.user_id == user.id,
        )
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")

    answers_result = await db.execute(
        select(CandidateAnswer)
        .where(CandidateAnswer.screening_id == screening_id)
        .options(joinedload(CandidateAnswer.question))
        .order_by(CandidateAnswer.created_at.asc())
    )
    answers = list(answers_result.scalars().unique().all())

    if not answers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No candidate answers to evaluate",
        )

    qa_pairs_text = _format_qa_pairs(answers)
    evaluation = await evaluate_interview_answers(qa_pairs_text)

    dialog = _merge_answers_evaluation_into_dialog_log(screening.dialog_log, evaluation)
    screening.dialog_log = dump_json_text(dialog)

    await db.commit()
    await db.refresh(screening)
    return screening, evaluation
