"""
Rubric service unit tests (no LLM / DB required for normalize).
Run: python tests_rubric.py
Optional API tests require server on http://127.0.0.1:8000
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime

import httpx

from app.services.rubric_service import normalize_rubric_json

BASE = "http://127.0.0.1:8000"
PASSWORD = "TestPassword123!"


def test_normalize_equal_weights_when_zero() -> None:
    data = normalize_rubric_json(
        {
            "competencies": [
                {"id": "a", "title": "A", "weight": 0, "must_have": False, "levels": {}},
                {"id": "b", "title": "B", "weight": 0, "must_have": True, "levels": {}},
            ]
        }
    )
    assert len(data["competencies"]) == 2
    assert abs(sum(c["weight"] for c in data["competencies"]) - 1.0) < 0.01


def test_normalize_rescales_weights() -> None:
    data = normalize_rubric_json(
        {
            "competencies": [
                {"id": "a", "title": "A", "weight": 0.3, "must_have": False, "levels": {}},
                {"id": "b", "title": "B", "weight": 0.3, "must_have": False, "levels": {}},
            ]
        }
    )
    total = sum(c["weight"] for c in data["competencies"])
    assert abs(total - 1.0) < 0.01


async def _login(client: httpx.AsyncClient, email: str) -> None:
    resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text


async def test_rubric_api_flow() -> None:
    ts = datetime.now().strftime("%H%M%S")
    email = f"rubric_{ts}@test.com"
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        reg = await client.post(
            "/auth/register",
            json={
                "agency_name": f"RubricAgency_{ts}",
                "email": email,
                "password": PASSWORD,
            },
        )
        if reg.status_code not in (200, 201):
            print(f"SKIP API rubric flow: register failed ({reg.status_code})")
            return

        await _login(client, email)

        vac = await client.post(
            "/vacancies/",
            json={
                "title": "Backend Dev",
                "company": "TestCo",
                "requirements": "Python, FastAPI",
                "description": "API development",
            },
        )
        assert vac.status_code == 201, vac.text
        vacancy_id = vac.json()["id"]

        overview = await client.get(f"/vacancies/{vacancy_id}/rubric")
        assert overview.status_code == 200
        assert overview.json()["draft"] is None
        assert overview.json()["approved"] is None

        gen = await client.post(f"/vacancies/{vacancy_id}/rubric/generate")
        if gen.status_code == 502:
            print("SKIP API rubric generate: LLM unavailable")
            return
        assert gen.status_code == 200, gen.text
        draft = gen.json()
        assert draft["status"] == "draft"
        assert len(draft["rubric_json"]["competencies"]) >= 1

        rubric_id = draft["id"]
        upd = await client.put(
            f"/vacancies/{vacancy_id}/rubric/{rubric_id}",
            json={
                "rubric_json": {
                    "competencies": [
                        {
                            "id": "skills",
                            "title": "Hard skills edited",
                            "weight": 0.5,
                            "must_have": True,
                            "levels": {"1": "low", "5": "high"},
                        },
                        {
                            "id": "exp",
                            "title": "Experience",
                            "weight": 0.5,
                            "must_have": False,
                            "levels": {},
                        },
                    ],
                    "generated_from": {},
                }
            },
        )
        assert upd.status_code == 200, upd.text
        assert upd.json()["rubric_json"]["competencies"][0]["title"] == "Hard skills edited"

        appr = await client.post(f"/vacancies/{vacancy_id}/rubric/{rubric_id}/approve")
        assert appr.status_code == 200, appr.text
        assert appr.json()["status"] == "approved"

        overview2 = await client.get(f"/vacancies/{vacancy_id}/rubric")
        assert overview2.status_code == 200
        body = overview2.json()
        assert body["approved"] is not None
        assert body["approved"]["status"] == "approved"

        gen2 = await client.post(f"/vacancies/{vacancy_id}/rubric/generate")
        assert gen2.status_code == 200, gen2.text
        overview3 = await client.get(f"/vacancies/{vacancy_id}/rubric")
        assert overview3.json()["draft"] is not None
        assert overview3.json()["approved"] is not None

    print("API rubric flow ok")


def main() -> int:
    test_normalize_equal_weights_when_zero()
    test_normalize_rescales_weights()
    print("unit tests ok")
    try:
        asyncio.run(test_rubric_api_flow())
    except (httpx.ConnectError, httpx.ReadTimeout):
        print("SKIP API rubric flow: server unavailable or LLM timeout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
