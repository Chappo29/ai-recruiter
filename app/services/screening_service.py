import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import LLM_PROMPT_VERSION, SCREENING_RUBRIC_PIPELINE, SCREENING_SHADOW_MODE
from app.core.config import STRUCTURED_INTERVIEW
from app.models import (
    Candidate,
    InterviewAnswer,
    Screening,
    ScreeningScore,
    User,
    Vacancy,
    VacancyInterviewQuestion,
)
from app.schemas.llm import RubricCompetency, ScoreBreakdown
from app.services.ai_audit_service import log_ai_decision
from app.services.llm_service import (
    extract_resume_profile,
    run_screening,
    score_by_rubric,
)
from app.services.rubric_service import build_vacancy_text, get_active_rubric, parse_rubric_json
from app.services.scoring_utils import (
    build_score_breakdown,
    compute_overall_score,
    verdict_from_score,
)
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


async def get_agency_vacancy(
    db: AsyncSession, vacancy_id: UUID, user: User
) -> Vacancy:
    result = await db.execute(
        select(Vacancy)
        .join(User, Vacancy.user_id == User.id)
        .where(Vacancy.id == vacancy_id, User.agency_id == user.agency_id)
    )
    vacancy = result.scalar_one_or_none()
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")
    return vacancy


async def get_user_vacancy(
    db: AsyncSession, vacancy_id: UUID, user: User
) -> Vacancy:
    return await get_agency_vacancy(db, vacancy_id, user)


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
        # "scoring" — resume parsing/LLM анализ в процессе, кандидат на
        # стадии «Оценка…». Перейдёт в "pending" в finalize_with_interview
        # после завершения интервью (или при таймауте).
        status="scoring",
    )
    db.add(screening)
    await db.commit()
    await db.refresh(screening)
    return screening


def _clamp_score(raw: int | None) -> int:
    if raw is None:
        return 0
    return int(max(0, min(100, int(raw))))


async def _persist_screening_result(
    db: AsyncSession,
    *,
    screening: Screening,
    vacancy: Vacancy,
    llm_result: dict,
    audit_extra: dict | None = None,
) -> int:
    """Apply LLM screening output; verdict always from code."""
    score = _clamp_score(llm_result.get("score"))
    screening.verdict = verdict_from_score(score)
    screening.score = score
    screening.summary = llm_result.get("summary")
    screening.ai_markers = dump_json_text(llm_result.get("ai_markers"))
    ai_dialog = _build_dialog_log(llm_result)
    if ai_dialog:
        screening.dialog_log = dump_json_text(
            merge_bot_dialog(
                screening.dialog_log,
                [{"role": "ai_analysis", "content": ai_dialog}],
            )
        )

    agency_id = vacancy.user.agency_id if vacancy.user is not None else None
    reasoning = {
        "summary": llm_result.get("summary"),
        "strengths": llm_result.get("strengths"),
        "weaknesses": llm_result.get("weaknesses"),
        "red_flags": llm_result.get("red_flags"),
        "ai_markers": llm_result.get("ai_markers"),
        "prompt_version": LLM_PROMPT_VERSION,
        "pipeline": "legacy",
    }
    if audit_extra:
        reasoning.update(audit_extra)

    await log_ai_decision(
        db,
        screening_id=screening.id,
        agency_id=agency_id,
        decision_type="screen",
        actor_type="ai",
        ai_score=score,
        ai_verdict=screening.verdict,
        reasoning=reasoning,
    )
    return score


async def _complete_legacy_screening(
    db: AsyncSession,
    *,
    screening: Screening,
    vacancy: Vacancy,
    resume_text: str,
) -> None:
    """PR #1 path: single LLM call + code-computed verdict."""
    vacancy_text = build_vacancy_text(vacancy)
    llm_result = await run_screening(vacancy_text, resume_text)
    await _persist_screening_result(db, screening=screening, vacancy=vacancy, llm_result=llm_result)


async def _run_rubric_screening(
    db: AsyncSession,
    *,
    screening: Screening,
    vacancy: Vacancy,
    resume_text: str,
) -> tuple[dict, ScreeningScore, ScoreBreakdown]:
    owner_result = await db.execute(select(User).where(User.id == vacancy.user_id))
    owner = owner_result.scalar_one_or_none()

    rubric = await get_active_rubric(db, vacancy, user=owner)
    rubric_data = parse_rubric_json(rubric)
    competencies = [
        RubricCompetency.model_validate(c) for c in (rubric_data.get("competencies") or [])
    ]

    vacancy_text = build_vacancy_text(vacancy)
    vacancy_summary = "\n".join(
        p for p in (vacancy.title, vacancy.requirements) if p
    )

    profile = await extract_resume_profile(resume_text, vacancy_summary)
    dim_result = await score_by_rubric(rubric_data, profile, vacancy_text)

    overall, bucket, must_have_failed = compute_overall_score(
        dim_result.dimensions, competencies
    )
    breakdown = build_score_breakdown(
        dim_result.dimensions, competencies, overall, bucket
    )

    llm_result = {
        "verdict": verdict_from_score(overall),
        "score": overall,
        "summary": dim_result.summary,
        "strengths": dim_result.strengths,
        "weaknesses": dim_result.weaknesses,
        "ai_markers": dim_result.ai_markers.model_dump(),
        "red_flags": dim_result.red_flags,
        "verification_questions": dim_result.verification_questions,
        "bucket": bucket,
        "must_have_failed": must_have_failed,
    }

    comp_map = {c.id: c for c in competencies}
    enriched_dims = [
        {
            **d.model_dump(),
            "title": comp_map[d.competency_id].title if d.competency_id in comp_map else d.competency_id,
            "weight": comp_map[d.competency_id].weight if d.competency_id in comp_map else 0.0,
        }
        for d in dim_result.dimensions
    ]

    score_row = ScreeningScore(
        screening_id=screening.id,
        rubric_id=rubric.id,
        rubric_version=rubric.version,
        extracted_profile_json=profile.model_dump_json(),
        dimension_scores_json=dump_json_text(enriched_dims),
        overall_score=overall,
        bucket=bucket,
        prompt_version=LLM_PROMPT_VERSION,
    )
    db.add(score_row)

    if STRUCTURED_INTERVIEW:
        try:
            existing_q = await db.execute(
                select(VacancyInterviewQuestion)
                .where(VacancyInterviewQuestion.vacancy_id == vacancy.id)
                .limit(1)
            )
            if existing_q.scalar_one_or_none() is None:
                from app.services.interview_service import sync_question_bank_for_rubric

                await sync_question_bank_for_rubric(
                    db,
                    rubric,
                    verification_questions=dim_result.verification_questions,
                )
        except Exception:
            logger.exception("Failed to sync interview question bank for %s", vacancy.id)

    return llm_result, score_row, breakdown


async def complete_screening(db: AsyncSession, screening_id: UUID) -> Screening:
    result = await db.execute(
        select(Screening)
        .options(
            joinedload(Screening.candidate),
            joinedload(Screening.vacancy).joinedload(Vacancy.user),
            joinedload(Screening.score_detail),
        )
        .where(Screening.id == screening_id)
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")

    vacancy = screening.vacancy
    candidate = screening.candidate

    if vacancy is None or candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening data not found")

    resume_text = candidate.resume_text
    if not resume_text or not resume_text.strip():
        screening.summary = "Не удалось извлечь текст резюме для анализа."
        screening.score = 0
        screening.verdict = verdict_from_score(0)
        await db.commit()
        await db.refresh(screening)
        return screening

    pending_score_row: ScreeningScore | None = None

    try:
        if SCREENING_RUBRIC_PIPELINE:
            llm_result, pending_score_row, _breakdown = await _run_rubric_screening(
                db,
                screening=screening,
                vacancy=vacancy,
                resume_text=resume_text,
            )

            if SCREENING_SHADOW_MODE:
                try:
                    legacy_result = await run_screening(
                        build_vacancy_text(vacancy), resume_text
                    )
                except Exception:
                    logger.exception("Legacy screening shadow failed for %s", screening_id)
                    legacy_result = None
            else:
                legacy_result = None

            await _persist_screening_result(
                db,
                screening=screening,
                vacancy=vacancy,
                llm_result=llm_result,
                audit_extra={
                    "pipeline": "rubric",
                    "bucket": llm_result.get("bucket"),
                    "shadow_score": legacy_result.get("score") if legacy_result else None,
                    "rubric_score": pending_score_row.overall_score,
                },
            )
        else:
            await _complete_legacy_screening(
                db,
                screening=screening,
                vacancy=vacancy,
                resume_text=resume_text,
            )
    except Exception:
        logger.exception("Screening LLM failed for %s", screening_id)
        if pending_score_row is not None:
            db.expunge(pending_score_row)
            pending_score_row = None
        try:
            await _complete_legacy_screening(
                db,
                screening=screening,
                vacancy=vacancy,
                resume_text=resume_text,
            )
        except Exception:
            screening.summary = "Ошибка анализа резюме (ИИ недоступен или вернул неверный ответ)."
            if screening.score is None:
                screening.score = 0
                screening.verdict = verdict_from_score(0)

    await db.commit()
    await db.refresh(screening)
    return screening


RESUME_WEIGHT = 0.6
INTERVIEW_WEIGHT = 0.4


async def finalize_with_interview(
    db: AsyncSession, screening_id: UUID
) -> Screening:
    """
    Combine resume score with interview answers and flip status: scoring → pending.
    Final score = 0.6 * resume_score + 0.4 * (avg(answer_1_5) * 20).
    If no interview answers — use resume score as-is. Idempotent: skips
    screenings whose status is no longer "scoring".
    """
    result = await db.execute(
        select(Screening)
        .options(joinedload(Screening.candidate))
        .where(Screening.id == screening_id)
    )
    screening = result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found"
        )

    if (screening.status or "").lower() != "scoring":
        return screening

    resume_score = _clamp_score(screening.score)

    answers_result = await db.execute(
        select(InterviewAnswer).where(InterviewAnswer.screening_id == screening_id)
    )
    answers = list(answers_result.scalars().all())
    scored = [a.score_1_5 for a in answers if a.score_1_5 is not None]

    if scored:
        avg_1_5 = sum(scored) / len(scored)
        interview_score = int(round(avg_1_5 * 20))
        combined = int(
            round(RESUME_WEIGHT * resume_score + INTERVIEW_WEIGHT * interview_score)
        )
    else:
        combined = resume_score

    combined = _clamp_score(combined)
    screening.score = combined
    screening.verdict = verdict_from_score(combined)
    screening.status = "pending"

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


def score_breakdown_for_screening(screening: Screening) -> ScoreBreakdown | None:
    detail = screening.score_detail
    if detail is None:
        return None

    dim_raw = parse_json_text(detail.dimension_scores_json)
    if not isinstance(dim_raw, list):
        return None

    from app.schemas.llm import ScoreBreakdownDimension

    dimensions = [
        ScoreBreakdownDimension(
            id=d.get("competency_id", ""),
            title=d.get("title") or d.get("competency_id"),
            score_1_5=int(d.get("score_1_5", 3)),
            weight=float(d.get("weight") or 0.0),
            evidence=d.get("evidence") or [],
        )
        for d in dim_raw
        if isinstance(d, dict)
    ]
    bucket = detail.bucket or "review"
    return ScoreBreakdown(bucket=bucket, dimensions=dimensions)
