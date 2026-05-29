"""
Structured interview runner unit tests (PR #4).
Run: python tests_interview_runner.py
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch


async def test_handle_structured_answer_advances_question() -> None:
    from bot.interview_runner import handle_structured_answer

    ud = {
        "screening_id": "00000000-0000-0000-0000-000000000001",
        "interview_questions": [
            {"id": "00000000-0000-0000-0000-000000000010", "question_text": "Q1", "competency_id": "a"},
            {"id": "00000000-0000-0000-0000-000000000011", "question_text": "Q2", "competency_id": "b"},
        ],
        "question_index": 0,
        "interview_turns": 0,
    }

    api_post = AsyncMock()

    with patch("bot.interview_runner.evaluate_answer") as eval_mock:
        eval_mock.return_value.score_1_5 = 4
        eval_mock.return_value.evidence = ["e1"]
        result = await handle_structured_answer(
            user_text="Ответ",
            ud=ud,
            api_post=api_post,
            agency_id="agency",
        )

    assert result["done"] is False
    assert result["message"] == "Q2"
    assert ud["question_index"] == 1
    assert ud["interview_turns"] == 1
    assert api_post.await_count == 1


async def test_handle_structured_answer_finishes_on_last_question() -> None:
    from bot.interview_runner import handle_structured_answer

    ud = {
        "screening_id": "00000000-0000-0000-0000-000000000001",
        "interview_questions": [
            {"id": "00000000-0000-0000-0000-000000000010", "question_text": "Q1", "competency_id": "a"},
        ],
        "question_index": 0,
        "interview_turns": 0,
    }

    api_post = AsyncMock()

    with patch("bot.interview_runner.evaluate_answer") as eval_mock:
        eval_mock.return_value.score_1_5 = 3
        eval_mock.return_value.evidence = []
        result = await handle_structured_answer(
            user_text="Ответ",
            ud=ud,
            api_post=api_post,
            agency_id="agency",
        )

    assert result["done"] is True
    assert ud["question_index"] == 1
    assert ud["interview_turns"] == 1


def main() -> int:
    asyncio.run(test_handle_structured_answer_advances_question())
    asyncio.run(test_handle_structured_answer_finishes_on_last_question())
    print("interview_runner tests ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

