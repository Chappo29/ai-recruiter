from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.config import get_internal_api_key
from app.deps import CurrentUser, DbSession
from app.models import CandidateAnswer, Question, Screening, Vacancy
from app.schemas.question import (
    AISuggestRequest,
    AISuggestResponse,
    AnswerCreate,
    AnswerResponse,
    QuestionCreate,
    QuestionResponse,
    QuestionUpdate,
)
from app.services import llm_service
from app.services.screening_service import get_user_vacancy

router = APIRouter(prefix="/questions", tags=["questions"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])

def _check_internal_key(x_internal_key: str) -> None:
    if x_internal_key != get_internal_api_key():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


async def _get_user_question(
    db: DbSession, question_id: UUID, current_user: CurrentUser
) -> Question:
    result = await db.execute(
        select(Question)
        .join(Vacancy, Question.vacancy_id == Vacancy.id)
        .where(Question.id == question_id, Vacancy.user_id == current_user.id)
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return question


def _vacancy_text(vacancy: Vacancy) -> str:
    parts = []
    if vacancy.requirements:
        parts.append(f"Требования:\n{vacancy.requirements}")
    if vacancy.description:
        parts.append(f"Описание:\n{vacancy.description}")
    return "\n\n".join(parts) if parts else vacancy.title


@router.get("/vacancy/{vacancy_id}", response_model=list[QuestionResponse])
async def list_questions_for_vacancy(
    vacancy_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[Question]:
    await get_user_vacancy(db, vacancy_id, current_user)

    result = await db.execute(
        select(Question)
        .where(Question.vacancy_id == vacancy_id)
        .order_by(Question.order_index.asc(), Question.created_at.asc())
    )
    return list(result.scalars().all())


@router.post("/", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
async def create_question(
    body: QuestionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> Question:
    await get_user_vacancy(db, body.vacancy_id, current_user)

    question = Question(
        vacancy_id=body.vacancy_id,
        text=body.text,
        order_index=body.order_index,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return question


@router.post("/ai-suggest", response_model=AISuggestResponse)
async def ai_suggest_questions(
    body: AISuggestRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> AISuggestResponse:
    vacancy = await get_user_vacancy(db, body.vacancy_id, current_user)
    vacancy_text = _vacancy_text(vacancy)
    if not vacancy_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vacancy has no requirements or description for AI suggestions",
        )

    try:
        result = await llm_service.suggest_interview_questions(vacancy_text)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM request failed: {exc}",
        ) from exc

    return AISuggestResponse(questions=result.get("questions", []))


@router.put("/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: UUID,
    body: QuestionUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Question:
    question = await _get_user_question(db, question_id, current_user)

    if body.text is not None:
        question.text = body.text
    if body.order_index is not None:
        question.order_index = body.order_index

    await db.commit()
    await db.refresh(question)
    return question


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    question = await _get_user_question(db, question_id, current_user)
    await db.delete(question)
    await db.commit()


@internal_router.get(
    "/questions/vacancy/{vacancy_id}",
    response_model=list[QuestionResponse],
)
async def list_questions_internal(
    vacancy_id: UUID,
    db: DbSession,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> list[Question]:
    _check_internal_key(x_internal_key)

    result = await db.execute(select(Vacancy).where(Vacancy.id == vacancy_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")

    result = await db.execute(
        select(Question)
        .where(Question.vacancy_id == vacancy_id)
        .order_by(Question.order_index.asc(), Question.created_at.asc())
    )
    return list(result.scalars().all())


@internal_router.post(
    "/answers/",
    response_model=AnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_answer_internal(
    body: AnswerCreate,
    db: DbSession,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> AnswerResponse:
    _check_internal_key(x_internal_key)

    screening_result = await db.execute(
        select(Screening).where(Screening.id == body.screening_id)
    )
    screening = screening_result.scalar_one_or_none()
    if screening is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")

    question_result = await db.execute(
        select(Question).where(
            Question.id == body.question_id,
            Question.vacancy_id == screening.vacancy_id,
        )
    )
    question = question_result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    existing_result = await db.execute(
        select(CandidateAnswer).where(
            CandidateAnswer.screening_id == body.screening_id,
            CandidateAnswer.question_id == body.question_id,
        )
    )
    answer = existing_result.scalar_one_or_none()

    if answer is None:
        answer = CandidateAnswer(
            screening_id=body.screening_id,
            question_id=body.question_id,
            answer_text=body.answer_text,
        )
        db.add(answer)
    else:
        answer.answer_text = body.answer_text

    await db.commit()
    await db.refresh(answer)

    return AnswerResponse(
        id=answer.id,
        screening_id=answer.screening_id,
        question_id=answer.question_id,
        question_text=question.text,
        answer_text=answer.answer_text,
        created_at=answer.created_at,
    )


@internal_router.get(
    "/answers/screening/{screening_id}",
    response_model=list[AnswerResponse],
)
async def list_answers_for_screening_internal(
    screening_id: UUID,
    db: DbSession,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
) -> list[AnswerResponse]:
    _check_internal_key(x_internal_key)

    screening_result = await db.execute(
        select(Screening).where(Screening.id == screening_id)
    )
    if screening_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening not found")

    result = await db.execute(
        select(CandidateAnswer)
        .where(CandidateAnswer.screening_id == screening_id)
        .options(joinedload(CandidateAnswer.question))
        .order_by(CandidateAnswer.created_at.asc())
    )
    answers = result.scalars().unique().all()

    return [
        AnswerResponse(
            id=answer.id,
            screening_id=answer.screening_id,
            question_id=answer.question_id,
            question_text=answer.question.text if answer.question else None,
            answer_text=answer.answer_text,
            created_at=answer.created_at,
        )
        for answer in answers
    ]
