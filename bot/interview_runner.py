"""Structured Telegram interview: fixed question bank, no generative questions."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Awaitable

import httpx

from app.services.llm_service import evaluate_answer
from app.utils.input_validation import validate_and_clean_candidate_input

logger = logging.getLogger(__name__)

_MAX_QUESTIONS = 5
_SCREENING_POLL_INTERVAL = 2.0
_SCREENING_POLL_TIMEOUT = 120.0


async def wait_for_screening_score(
    api_get: Callable[..., Awaitable[httpx.Response]],
    *,
    screening_id: str,
    agency_id: str,
) -> dict[str, Any] | None:
    """Poll until screening has a score or timeout."""
    deadline = time.monotonic() + _SCREENING_POLL_TIMEOUT
    async with httpx.AsyncClient(timeout=30.0) as client:
        while time.monotonic() < deadline:
            resp = await api_get(
                client,
                f"/internal/screenings/{screening_id}",
                agency_id=agency_id,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("score") is not None:
                    return data
            await asyncio.sleep(_SCREENING_POLL_INTERVAL)
    return None


async def load_interview_questions(
    api_get: Callable[..., Awaitable[httpx.Response]],
    *,
    vacancy_id: str,
    agency_id: str,
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await api_get(
            client,
            f"/internal/vacancies/{vacancy_id}/interview-questions",
            agency_id=agency_id,
        )
        if resp.status_code != 200:
            logger.warning("Failed to load interview questions: %s", resp.text)
            return []
        return resp.json()


async def ensure_question_bank(
    api_post: Callable[..., Awaitable[httpx.Response]],
    *,
    vacancy_id: str,
    agency_id: str,
) -> list[dict[str, Any]]:
    """Ask backend to create a default question bank if vacancy has none."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await api_post(
            client,
            f"/internal/vacancies/{vacancy_id}/ensure-interview-questions",
            {"agency_id": agency_id},
        )
        if resp.status_code != 200:
            logger.warning("ensure-interview-questions failed: %s", resp.text)
            return []
        return resp.json()


async def finalize_screening(
    api_post: Callable[..., Awaitable[httpx.Response]],
    *,
    screening_id: str,
    agency_id: str,
) -> None:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await api_post(
                client,
                f"/internal/screenings/{screening_id}/finalize",
                {"agency_id": agency_id},
            )
            if resp.status_code >= 400:
                logger.warning("finalize screening failed: %s", resp.text)
    except Exception:
        logger.exception("finalize screening request failed for %s", screening_id)


def format_opening_message(first_name: str, question_text: str) -> str:
    return f"Спасибо, {first_name}!\n\n{question_text}"


async def handle_structured_answer(
    *,
    user_text: str,
    ud: dict[str, Any],
    api_post: Callable[..., Awaitable[httpx.Response]],
    agency_id: str,
) -> dict[str, Any]:
    """
    Process one candidate answer in structured mode.
    Returns {message, done, early_exit?}.
    """
    validation = validate_and_clean_candidate_input(
        user_text, max_length=500, check_injection=True
    )
    cleaned = validation["cleaned"]

    if cleaned == "[PROFANITY_DETECTED]" or not validation["is_safe"]:
        return {
            "message": "Спасибо за время! Передам вашу анкету рекрутеру.",
            "done": True,
            "early_exit": True,
        }

    questions: list[dict] = ud.get("interview_questions") or []
    q_index = int(ud.get("question_index") or 0)
    if q_index >= len(questions):
        return {"message": "", "done": True}

    current_q = questions[q_index]
    screening_id = ud.get("screening_id")

    score_1_5 = None
    evidence: list[str] = []
    try:
        evaluation = await evaluate_answer(
            current_q.get("question_text", ""),
            cleaned,
            competency_title=current_q.get("competency_id"),
        )
        score_1_5 = evaluation.score_1_5
        evidence = evaluation.evidence
    except Exception:
        logger.exception("Answer evaluation failed")

    if screening_id:
        async with httpx.AsyncClient(timeout=60.0) as client:
            await api_post(
                client,
                f"/internal/screenings/{screening_id}/interview-answers",
                {
                    "agency_id": agency_id,
                    "question_id": current_q.get("id"),
                    "answer_text": cleaned,
                    "score_1_5": score_1_5,
                    "evidence": evidence,
                },
            )

    next_index = q_index + 1
    ud["question_index"] = next_index
    turns = int(ud.get("interview_turns") or 0) + 1
    ud["interview_turns"] = turns

    if next_index >= len(questions) or next_index >= _MAX_QUESTIONS or turns >= _MAX_QUESTIONS:
        return {"message": "", "done": True}

    next_q = questions[next_index]
    return {
        "message": next_q.get("question_text", ""),
        "done": False,
    }


async def start_structured_interview(
    *,
    ud: dict[str, Any],
    api_get: Callable[..., Awaitable[httpx.Response]],
    api_post: Callable[..., Awaitable[httpx.Response]],
    first_name: str,
    vacancy_id: str,
    agency_id: str,
    screening_id: str,
) -> dict[str, Any] | None:
    """
    Wait for the resume score to be available, then load (or generate on
    the fly) the structured question bank for this vacancy. Returns the
    first turn, or None if no bank could be produced — in that case the
    caller should finalize the screening with the resume-only score.
    """
    await wait_for_screening_score(
        api_get,
        screening_id=screening_id,
        agency_id=agency_id,
    )

    questions = await load_interview_questions(
        api_get, vacancy_id=vacancy_id, agency_id=agency_id
    )
    if not questions:
        questions = await ensure_question_bank(
            api_post, vacancy_id=vacancy_id, agency_id=agency_id
        )
    if not questions:
        return None

    questions = questions[:_MAX_QUESTIONS]
    ud["interview_questions"] = questions
    ud["question_index"] = 0

    first_q = questions[0].get("question_text", "")
    return {
        "message": format_opening_message(first_name, first_q),
        "done": False,
    }


def use_structured_mode(ud: dict[str, Any]) -> bool:
    return bool(ud.get("interview_questions"))
