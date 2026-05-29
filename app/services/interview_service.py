"""Structured interview question bank and answer storage."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InterviewAnswer, Vacancy, VacancyInterviewQuestion, VacancyRubric
from app.schemas.llm import RubricCompetency
from app.services.llm_service import suggest_interview_questions
from app.services.rubric_service import build_vacancy_text, parse_rubric_json
from app.utils.json_fields import dump_json_text, parse_json_text

logger = logging.getLogger(__name__)

MOTIVATION_QUESTIONS = (
    "Почему вас заинтересовала эта позиция?",
    "Что для вас важно в новой роли?",
)


async def sync_question_bank_for_rubric(
    db: AsyncSession,
    rubric: VacancyRubric,
    *,
    verification_questions: list[str] | None = None,
) -> list[VacancyInterviewQuestion]:
    """Rebuild question bank for vacancy from rubric + verification questions."""
    result = await db.execute(
        select(Vacancy).where(Vacancy.id == rubric.vacancy_id)
    )
    vacancy = result.scalar_one_or_none()
    if vacancy is None:
        return []

    await db.execute(
        delete(VacancyInterviewQuestion).where(
            VacancyInterviewQuestion.vacancy_id == rubric.vacancy_id
        )
    )

    questions: list[VacancyInterviewQuestion] = []
    order = 0

    for text in MOTIVATION_QUESTIONS:
        questions.append(
            VacancyInterviewQuestion(
                vacancy_id=rubric.vacancy_id,
                rubric_id=rubric.id,
                competency_id="motivation",
                question_text=text,
                sort_order=order,
                required=True,
                source="motivation",
            )
        )
        order += 1

    for idx, text in enumerate((verification_questions or [])[:3]):
        if not text.strip():
            continue
        questions.append(
            VacancyInterviewQuestion(
                vacancy_id=rubric.vacancy_id,
                rubric_id=rubric.id,
                competency_id="verification",
                question_text=text.strip(),
                sort_order=order,
                required=idx == 0,
                source="verification",
            )
        )
        order += 1

    rubric_data = parse_rubric_json(rubric)
    competencies_raw = rubric_data.get("competencies") or []
    competency_questions: list[str] = []
    try:
        suggested = await suggest_interview_questions(build_vacancy_text(vacancy))
        competency_questions = suggested.get("questions") or []
    except Exception:
        logger.exception("Failed to suggest competency questions")

    comp_ids = [
        c.get("id", f"comp_{i}") for i, c in enumerate(competencies_raw)
    ]
    for i, text in enumerate(competency_questions[:3]):
        comp_id = comp_ids[i % len(comp_ids)] if comp_ids else None
        questions.append(
            VacancyInterviewQuestion(
                vacancy_id=rubric.vacancy_id,
                rubric_id=rubric.id,
                competency_id=comp_id,
                question_text=text,
                sort_order=order,
                required=False,
                source="rubric",
            )
        )
        order += 1

    for comp_raw in competencies_raw[:2]:
        comp = RubricCompetency.model_validate(comp_raw)
        fallback_q = f"Расскажите, пожалуйста, о вашем опыте: {comp.title.lower()}?"
        questions.append(
            VacancyInterviewQuestion(
                vacancy_id=rubric.vacancy_id,
                rubric_id=rubric.id,
                competency_id=comp.id,
                question_text=fallback_q,
                sort_order=order,
                required=comp.must_have,
                source="rubric",
            )
        )
        order += 1

    for q in questions:
        db.add(q)
    await db.commit()
    return questions


GENERIC_FALLBACK_QUESTIONS = (
    "Почему вас заинтересовала эта позиция?",
    "Расскажите о вашем релевантном опыте, который пригодится в этой роли.",
    "Какие задачи в работе вас мотивируют больше всего?",
    "Какие у вас ожидания по уровню дохода и формату работы?",
)


async def ensure_question_bank(
    db: AsyncSession, vacancy_id: UUID
) -> list[VacancyInterviewQuestion]:
    """
    Guarantee a usable interview question bank for a vacancy.
    1. If questions already exist — return them.
    2. If an active rubric exists — sync from rubric (existing path).
    3. Otherwise — generate 3 vacancy-aware questions via LLM and prepend
       2 motivational questions; persist them all as a generic bank.
    Used by the bot before structured interview starts so we never fall
    through to a generative free-form interview.
    """
    existing = await list_interview_questions(db, vacancy_id)
    if existing:
        return existing

    vacancy = (
        await db.execute(select(Vacancy).where(Vacancy.id == vacancy_id))
    ).scalar_one_or_none()
    if vacancy is None:
        return []

    rubric_row = (
        await db.execute(
            select(VacancyRubric)
            .where(
                VacancyRubric.vacancy_id == vacancy_id,
                VacancyRubric.status == "approved",
            )
            .order_by(VacancyRubric.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if rubric_row is not None:
        return await sync_question_bank_for_rubric(db, rubric_row)

    vacancy_text = build_vacancy_text(vacancy)
    suggested_questions: list[str] = []
    try:
        suggested = await suggest_interview_questions(vacancy_text)
        suggested_questions = [
            q for q in (suggested.get("questions") or []) if q and q.strip()
        ][:3]
    except Exception:
        logger.exception("LLM question suggestion failed for vacancy %s", vacancy_id)

    questions: list[VacancyInterviewQuestion] = []
    order = 0
    for text in MOTIVATION_QUESTIONS:
        questions.append(
            VacancyInterviewQuestion(
                vacancy_id=vacancy_id,
                rubric_id=None,
                competency_id="motivation",
                question_text=text,
                sort_order=order,
                required=True,
                source="motivation",
            )
        )
        order += 1

    fill_with = suggested_questions or list(GENERIC_FALLBACK_QUESTIONS[:3])
    for text in fill_with[:3]:
        questions.append(
            VacancyInterviewQuestion(
                vacancy_id=vacancy_id,
                rubric_id=None,
                competency_id=None,
                question_text=text.strip(),
                sort_order=order,
                required=False,
                source="generic",
            )
        )
        order += 1

    for q in questions:
        db.add(q)
    await db.commit()
    return questions


async def list_interview_questions(
    db: AsyncSession, vacancy_id: UUID
) -> list[VacancyInterviewQuestion]:
    result = await db.execute(
        select(VacancyInterviewQuestion)
        .where(VacancyInterviewQuestion.vacancy_id == vacancy_id)
        .order_by(VacancyInterviewQuestion.sort_order)
    )
    return list(result.scalars().all())


async def save_interview_answer(
    db: AsyncSession,
    *,
    screening_id: UUID,
    question_id: UUID,
    answer_text: str,
    score_1_5: int | None = None,
    evidence: list[str] | None = None,
) -> InterviewAnswer:
    entry = InterviewAnswer(
        screening_id=screening_id,
        question_id=question_id,
        answer_text=answer_text,
        score_1_5=score_1_5,
        evidence_json=dump_json_text(evidence) if evidence else None,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


def competency_title_for_question(
    rubric_json: dict, competency_id: str | None
) -> str | None:
    if not competency_id:
        return None
    for comp in rubric_json.get("competencies") or []:
        if comp.get("id") == competency_id:
            return comp.get("title")
    return competency_id
