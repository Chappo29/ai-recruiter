"""
Unit tests for PR #1 LLM hardening (no Ollama required).
Run: python tests_llm_hardening.py
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

from app.schemas.llm import ScreeningLLMResult
from app.services.llm_client import _parse_json_raw
from app.services.llm_service import _normalize_screening_result
from app.services.scoring_utils import bucket_from_score, verdict_from_score


def test_parse_json_raw_strips_fences() -> None:
    raw = '```json\n{"score": 80, "summary": "ok"}\n```'
    data = _parse_json_raw(raw)
    assert data["score"] == 80


def test_verdict_from_score_thresholds() -> None:
    assert verdict_from_score(80) == "fit"
    assert verdict_from_score(75) == "fit"
    assert verdict_from_score(74) == "maybe"
    assert verdict_from_score(50) == "maybe"
    assert verdict_from_score(49) == "reject"
    assert verdict_from_score(0) == "reject"


def test_bucket_from_score() -> None:
    assert bucket_from_score(80) == "recommended"
    assert bucket_from_score(60) == "review"
    assert bucket_from_score(30) == "weak"


def test_normalize_screening_overrides_llm_verdict() -> None:
    result = ScreeningLLMResult(
        verdict="fit",
        score=40,
        summary="test",
    )
    normalized = _normalize_screening_result(result)
    assert normalized["score"] == 40
    assert normalized["verdict"] == "reject"


def test_normalize_screening_clamps_score() -> None:
    result = ScreeningLLMResult(score=150, summary="x")
    normalized = _normalize_screening_result(result)
    assert normalized["score"] == 100
    assert normalized["verdict"] == "fit"


async def test_generate_json_retries_on_invalid_json() -> None:
    from unittest.mock import MagicMock

    from app.services.llm_client import generate_json

    def make_response(body: str):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"response": body}
        return resp

    post = AsyncMock(
        side_effect=[
            make_response("not json"),
            make_response(json.dumps({"score": 70, "summary": "ok"})),
        ]
    )

    with patch("app.services.llm_client.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__.return_value.post = post
        result = await generate_json('{"prompt": "test"}', schema=ScreeningLLMResult)

    assert result.score == 70
    assert post.await_count == 2


def run_sync_tests() -> None:
    test_parse_json_raw_strips_fences()
    test_verdict_from_score_thresholds()
    test_bucket_from_score()
    test_normalize_screening_overrides_llm_verdict()
    test_normalize_screening_clamps_score()
    print("sync tests ok")


async def run_async_tests() -> None:
    await test_generate_json_retries_on_invalid_json()
    print("async tests ok")


def main() -> int:
    run_sync_tests()
    asyncio.run(run_async_tests())
    print("all PR #1 hardening tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
