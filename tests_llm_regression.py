"""
LLM regression tests against golden fixtures.
Run: python tests_llm_regression.py
Requires Ollama at OLLAMA_URL (default localhost:11434).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.core.load_env import load_project_env
from app.services.rubric_service import build_vacancy_text
from app.schemas.llm import RubricCompetency
from app.services.llm_service import extract_resume_profile, run_screening, score_by_rubric
from app.services.scoring_utils import bucket_from_score, compute_overall_score

load_project_env()

FIXTURES = Path(__file__).resolve().parent / "tests" / "fixtures" / "golden"


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _load_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class VacancyStub:
    def __init__(self, data: dict):
        self.title = data.get("title", "")
        self.requirements = data.get("requirements")
        self.description = data.get("description")
        self.ai_screening_prompt = data.get("ai_screening_prompt")


async def _run_rubric_case(
    *, vacancy_text: str, resume: str, rubric_json: dict
) -> tuple[int, str, str]:
    vacancy_summary = "\n".join(
        [line for line in [vacancy_text[:4000]] if line]
    )
    profile = await extract_resume_profile(resume, vacancy_summary)
    dim_result = await score_by_rubric(rubric_json, profile, vacancy_text)
    competencies = [
        RubricCompetency.model_validate(c)
        for c in (rubric_json.get("competencies") or [])
    ]
    overall, bucket, _ = compute_overall_score(dim_result.dimensions, competencies)
    verdict = "fit" if overall >= 75 else "maybe" if overall >= 50 else "reject"
    return overall, bucket, verdict


async def run_case(name: str, resume_file: str, expected_file: str) -> bool:
    vacancy_data = _load_json("python_dev_vacancy.json")
    rubric_json = _load_json("default_rubric.json")
    resume = _load_text(resume_file)
    expected = _load_json(expected_file)
    vacancy = VacancyStub(vacancy_data)
    vacancy_text = build_vacancy_text(vacancy)

    print(f"Running case: {name}...")
    try:
        overall, bucket, verdict = await _run_rubric_case(
            vacancy_text=vacancy_text, resume=resume, rubric_json=rubric_json
        )
    except Exception as exc:
        print(f"  FAIL: LLM error: {exc}")
        return False

    score_ok = expected["score_min"] <= overall <= expected["score_max"]
    bucket_ok = bucket == expected.get("bucket") or not expected.get("bucket")

    if score_ok and bucket_ok:
        print(f"  OK: score={overall}, bucket={bucket}, verdict={verdict}")
        return True

    print(
        f"  FAIL: score={overall} (expected {expected['score_min']}-{expected['score_max']}), "
        f"bucket={bucket} (expected {expected.get('bucket')})"
    )
    # Also show legacy score for debugging drift (doesn't fail the test).
    try:
        legacy = await run_screening(vacancy_text, resume)
        legacy_score = int(legacy.get("score") or 0)
        legacy_bucket = bucket_from_score(legacy_score)
        print(f"    legacy: score={legacy_score}, bucket={legacy_bucket}, verdict={legacy.get('verdict')}")
    except Exception:
        pass
    return False


async def main() -> int:
    cases = [
        ("strong_python", "strong_python_resume.txt", "strong_python_expected.json"),
        ("weak_match", "weak_match_resume.txt", "weak_match_expected.json"),
    ]
    results = []
    for name, resume, expected in cases:
        ok = await run_case(name, resume, expected)
        results.append(ok)
    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} golden cases passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
