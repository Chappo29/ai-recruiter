"""
Regression / security smoke tests for RecruitAI API.
Run: python tests_security.py
Requires API on http://127.0.0.1:8000 and .env with INTERNAL_API_KEY.
"""
import asyncio
import os
import time
import uuid

import httpx

from app.core.load_env import load_project_env

load_project_env()

BASE = "http://127.0.0.1:8000"
INTERNAL_KEY = os.getenv("INTERNAL_API_KEY", "")

KNOWN_RESUME_ID = "a4720b67-d9a4-4877-a934-be77e34181fb"


class SecurityTests:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def ok(self, name: str, msg: str = ""):
        self.passed += 1
        print(f"[OK] {name}" + (f": {msg}" if msg else ""))

    def fail(self, name: str, msg: str):
        self.failed += 1
        print(f"[FAIL] {name}: {msg}")

    def warn(self, name: str, msg: str):
        self.warnings += 1
        print(f"[WARN] {name}: {msg}")

    async def run_all(self):
        print("\n" + "=" * 60)
        print("SECURITY / REGRESSION TESTS")
        print("=" * 60 + "\n")

        await self.test_public_media_blocked()
        await self.test_protected_resume_requires_auth()
        await self.test_health_minimal()
        await self.test_internal_key_compare_digest()
        await self.test_invitations_no_token_in_list()
        await self.test_invite_invalid_role_rejected()
        await self.test_internal_candidate_requires_agency()
        await self.test_internal_screening_agency_mismatch()
        await self.test_reminder_cancel_scoped_by_agency()
        await self.test_cookie_auth_flow()
        await self.test_public_create_candidate_removed()
        await self.test_bot_state_no_resume_text()

        print("\n" + "=" * 60)
        print(f"PASS={self.passed} FAIL={self.failed} WARN={self.warnings}")
        print("=" * 60 + "\n")
        return self.failed == 0

    async def test_public_media_blocked(self):
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{BASE}/media/resumes/{KNOWN_RESUME_ID}.pdf")
            if r.status_code == 404:
                self.ok("public_media_blocked", "GET /media/resumes -> 404")
            else:
                self.fail("public_media_blocked", f"expected 404, got {r.status_code}")

    async def test_protected_resume_requires_auth(self):
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{BASE}/candidates/{KNOWN_RESUME_ID}/resume")
            if r.status_code == 401:
                self.ok("resume_requires_auth", "401 without token")
            else:
                self.fail("resume_requires_auth", f"expected 401, got {r.status_code}")

    async def test_health_minimal(self):
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{BASE}/health")
            data = r.json()
            if r.status_code == 200 and data == {"status": "ok"}:
                self.ok("health_minimal", "no bot_worker_url leak")
            elif "bot_worker_url" in data:
                self.fail("health_minimal", "bot_worker_url still exposed")
            else:
                self.fail("health_minimal", str(data))

    async def test_internal_key_compare_digest(self):
        async with httpx.AsyncClient() as c:
            r = await c.get(
                f"{BASE}/internal/vacancies/",
                headers={"X-Internal-Key": "wrong-key"},
                params={"agency_id": str(uuid.uuid4())},
            )
            if r.status_code == 403:
                self.ok("internal_bad_key", "403 on wrong key")
            else:
                self.fail("internal_bad_key", f"expected 403, got {r.status_code}")

    async def _register_admin(self, c: httpx.AsyncClient) -> tuple[str, str]:
        ts = str(int(time.time()))
        email = f"sec_{ts}@test.com"
        r = await c.post(
            f"{BASE}/auth/register",
            json={
                "agency_name": f"SecAgency_{ts}",
                "email": email,
                "password": "TestPassword123!",
            },
        )
        if r.status_code != 201:
            raise RuntimeError(f"register failed: {r.text}")
        login = await c.post(
            f"{BASE}/auth/login",
            json={"email": email, "password": "TestPassword123!"},
        )
        if login.status_code != 200:
            raise RuntimeError(f"login failed: {login.text}")
        token = login.json()["access_token"]
        return token, ts

    async def test_invitations_no_token_in_list(self):
        async with httpx.AsyncClient() as c:
            token, _ = await self._register_admin(c)
            await c.post(
                f"{BASE}/team/invite",
                headers={"Authorization": f"Bearer {token}"},
                json={"email": f"invited_{int(time.time())}@test.com", "role": "recruiter"},
            )
            r = await c.get(
                f"{BASE}/team/invitations",
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code != 200:
                self.fail("invitations_list", r.text)
                return
            items = r.json()
            if not items:
                self.warn("invitations_list", "no invitations returned")
                return
            if any("token" in item for item in items):
                self.fail("invitations_no_token", "token field still in list response")
            else:
                self.ok("invitations_no_token", "list has email/role only")

    async def test_invite_invalid_role_rejected(self):
        async with httpx.AsyncClient() as c:
            token, _ = await self._register_admin(c)
            r = await c.post(
                f"{BASE}/team/invite",
                headers={"Authorization": f"Bearer {token}"},
                json={"email": f"badrole_{int(time.time())}@test.com", "role": "superadmin"},
            )
            if r.status_code == 422:
                self.ok("invite_invalid_role", "422 on bad role")
            else:
                self.fail("invite_invalid_role", f"expected 422, got {r.status_code}")

    async def test_internal_candidate_requires_agency(self):
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{BASE}/internal/candidates/",
                headers={"X-Internal-Key": INTERNAL_KEY},
                json={"telegram_id": "999001", "full_name": "Test User"},
            )
            if r.status_code == 400:
                self.ok("candidate_requires_agency_id")
            else:
                self.fail("candidate_requires_agency_id", f"expected 400, got {r.status_code}")

    async def test_internal_screening_agency_mismatch(self):
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{BASE}/internal/screenings/",
                headers={"X-Internal-Key": INTERNAL_KEY},
                json={
                    "agency_id": str(uuid.uuid4()),
                    "vacancy_id": str(uuid.uuid4()),
                    "candidate_id": str(uuid.uuid4()),
                },
            )
            if r.status_code == 404:
                self.ok("screening_agency_mismatch", "404 when resources not in agency")
            else:
                self.fail("screening_agency_mismatch", f"expected 404, got {r.status_code}")

    async def test_reminder_cancel_scoped_by_agency(self):
        tg = f"sec_rem_{int(time.time())}"
        agency_a = str(uuid.uuid4())
        agency_b = str(uuid.uuid4())
        async with httpx.AsyncClient() as c:
            for agency in (agency_a, agency_b):
                r = await c.post(
                    f"{BASE}/internal/reminders/",
                    headers={"X-Internal-Key": INTERNAL_KEY},
                    json={
                        "telegram_id": tg,
                        "agency_id": agency,
                        "state": "waiting_resume",
                        "vacancy_title": "Test",
                    },
                )
                if r.status_code not in (200, 201):
                    self.fail("reminder_create", r.text)
                    return

            cancel = await c.post(
                f"{BASE}/internal/reminders/cancel",
                headers={"X-Internal-Key": INTERNAL_KEY},
                json={"telegram_id": tg, "agency_id": agency_a},
            )
            if cancel.status_code != 200 or cancel.json().get("cancelled") != 1:
                self.fail("reminder_cancel_scope", cancel.text)
                return

            # Agency B reminder should still exist (not cancelled)
            # No public list endpoint — recreate cancel for B should find 1
            cancel_b = await c.post(
                f"{BASE}/internal/reminders/cancel",
                headers={"X-Internal-Key": INTERNAL_KEY},
                json={"telegram_id": tg, "agency_id": agency_b},
            )
            if cancel_b.status_code == 200 and cancel_b.json().get("cancelled") == 1:
                self.ok("reminder_cancel_scope", "only target agency cancelled")
            else:
                self.fail("reminder_cancel_scope", cancel_b.text)

    async def test_cookie_auth_flow(self):
        async with httpx.AsyncClient() as c:
            ts = str(int(time.time()))
            email = f"cookie_{ts}@test.com"
            await c.post(
                f"{BASE}/auth/register",
                json={
                    "agency_name": f"CookieAgency_{ts}",
                    "email": email,
                    "password": "TestPassword123!",
                },
            )
            login = await c.post(
                f"{BASE}/auth/login",
                json={"email": email, "password": "TestPassword123!"},
            )
            if login.status_code != 200:
                self.fail("cookie_login", login.text)
                return
            cookie = login.cookies.get("access_token")
            if not cookie:
                self.fail("cookie_login", "no access_token cookie set")
                return
            me = await c.get(f"{BASE}/auth/me", cookies=login.cookies)
            if me.status_code == 200:
                self.ok("cookie_auth_me", "auth via HttpOnly cookie")
            else:
                self.fail("cookie_auth_me", f"status {me.status_code}")

    async def test_public_create_candidate_removed(self):
        async with httpx.AsyncClient() as c:
            token, _ = await self._register_admin(c)
            r = await c.post(
                f"{BASE}/candidates/",
                headers={"Authorization": f"Bearer {token}"},
                json={"full_name": "Should Fail", "telegram_id": "12345"},
            )
            if r.status_code == 405:
                self.ok("public_create_candidate_removed", "405 Method Not Allowed")
            elif r.status_code == 404:
                self.ok("public_create_candidate_removed", "404 route removed")
            else:
                self.fail("public_create_candidate_removed", f"got {r.status_code}")

    async def test_bot_state_no_resume_text(self):
        from app.services import bot_state_service

        payload = bot_state_service.serialize_user_data(
            {
                "vacancy_id": "v1",
                "resume_text": "secret resume content",
                "full_name": "Test",
            }
        )
        if "resume_text" not in payload:
            self.ok("bot_state_no_resume_text")
        else:
            self.fail("bot_state_no_resume_text", "resume_text still persisted")


if __name__ == "__main__":
    ok = asyncio.run(SecurityTests().run_all())
    raise SystemExit(0 if ok else 1)
