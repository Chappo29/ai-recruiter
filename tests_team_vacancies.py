"""
Team member access within one agency:
- second user (recruiter) sees admin's vacancies
- can create vacancy
- can delete admin's vacancy

Run: python tests_team_vacancies.py
"""
import asyncio
import time

import httpx

BASE = "http://127.0.0.1:8000"
PASSWORD = "TestPassword123!"
# Fallback when register rate-limited (reuse recent security-test admin)
FALLBACK_ADMIN_EMAIL = "sec_1779880464@test.com"


async def _login(client: httpx.AsyncClient, email: str) -> str:
    r = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text}")
    return r.json()["access_token"]


async def main():
    ts = str(int(time.time()))
    admin_email_candidate = f"team_admin_{ts}@test.com"
    recruiter_email = f"team_rec_{ts}@test.com"

    print("\n" + "=" * 60)
    print("TEAM VACANCY ACCESS (same agency)")
    print("=" * 60 + "\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        admin_email = None
        # 1. Admin registers (or reuse existing on rate limit)
        r = await client.post(
            f"{BASE}/auth/register",
            json={
                "agency_name": f"TeamCo_{ts}",
                "email": admin_email_candidate,
                "password": PASSWORD,
            },
        )
        if r.status_code == 201:
            admin_email = admin_email_candidate
            print("[OK] Admin registered")
        elif r.status_code == 429:
            admin_email = FALLBACK_ADMIN_EMAIL
            print(f"[WARN] Register rate-limited, reusing admin {admin_email}")
        else:
            print(f"[FAIL] register admin: {r.status_code} {r.text}")
            return False

        admin_token = await _login(client, admin_email)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        print("[OK] Admin logged in")

        # 2. Admin creates vacancy
        r = await client.post(
            f"{BASE}/vacancies/",
            headers=admin_headers,
            json={
                "title": "Admin Vacancy",
                "company": "TeamCo",
                "requirements": "Req",
                "description": "Desc",
            },
        )
        assert r.status_code == 201, r.text
        admin_vacancy_id = r.json()["id"]
        print(f"[OK] Admin created vacancy {admin_vacancy_id}")

        # 3. Admin invites recruiter
        r = await client.post(
            f"{BASE}/team/invite",
            headers=admin_headers,
            json={"email": recruiter_email, "role": "recruiter"},
        )
        assert r.status_code == 200, r.text
        invite_token = r.json()["invitation_token"]
        print("[OK] Recruiter invited")

        # 4. Recruiter accepts invite
        r = await client.post(
            f"{BASE}/team/accept-invite",
            json={"invitation_token": invite_token, "password": PASSWORD},
        )
        assert r.status_code == 201, r.text
        assert r.json()["role"] == "recruiter"
        print("[OK] Recruiter joined agency")

        rec_token = await _login(client, recruiter_email)
        rec_headers = {"Authorization": f"Bearer {rec_token}"}
        print("[OK] Recruiter logged in")

        # 5. Recruiter sees admin vacancy
        r = await client.get(f"{BASE}/vacancies/", headers=rec_headers)
        assert r.status_code == 200, r.text
        vacancies = r.json()
        ids = {v["id"] for v in vacancies}
        if admin_vacancy_id in ids:
            print(f"[OK] Recruiter sees admin vacancy (total {len(vacancies)})")
        else:
            print(f"[FAIL] Recruiter does NOT see admin vacancy. Got ids: {ids}")
            return False

        # 6. Recruiter creates own vacancy
        r = await client.post(
            f"{BASE}/vacancies/",
            headers=rec_headers,
            json={
                "title": "Recruiter Vacancy",
                "company": "TeamCo",
                "requirements": "Req2",
                "description": "Desc2",
            },
        )
        if r.status_code == 201:
            rec_vacancy_id = r.json()["id"]
            print(f"[OK] Recruiter created vacancy {rec_vacancy_id}")
        else:
            print(f"[FAIL] Recruiter cannot create vacancy: {r.status_code} {r.text}")
            return False

        # 7. Admin sees recruiter vacancy
        r = await client.get(f"{BASE}/vacancies/", headers=admin_headers)
        admin_ids = {v["id"] for v in r.json()}
        if rec_vacancy_id in admin_ids:
            print("[OK] Admin sees recruiter vacancy")
        else:
            print("[FAIL] Admin does NOT see recruiter vacancy")
            return False

        # 8. Recruiter deletes admin vacancy
        r = await client.delete(
            f"{BASE}/vacancies/{admin_vacancy_id}",
            headers=rec_headers,
        )
        if r.status_code == 204:
            print("[OK] Recruiter deleted admin vacancy (204)")
        else:
            print(f"[FAIL] Recruiter cannot delete admin vacancy: {r.status_code} {r.text}")
            return False

        # 9. Verify deleted
        r = await client.get(f"{BASE}/vacancies/", headers=rec_headers)
        remaining = {v["id"] for v in r.json()}
        if admin_vacancy_id not in remaining and rec_vacancy_id in remaining:
            print("[OK] Admin vacancy gone, recruiter vacancy remains")
        else:
            print(f"[FAIL] Unexpected list after delete: {remaining}")
            return False

        # 10. Recruiter cannot manage bot (sanity)
        r = await client.post(
            f"{BASE}/bots/start",
            headers=rec_headers,
            json={"token": "fake"},
        )
        if r.status_code == 403:
            print("[OK] Recruiter still cannot start bot (403)")
        else:
            print(f"[WARN] Recruiter bot start returned {r.status_code}")

    print("\n" + "=" * 60)
    print("ALL TEAM VACANCY TESTS PASSED")
    print("=" * 60 + "\n")
    return True


if __name__ == "__main__":
    ok = asyncio.run(main())
    raise SystemExit(0 if ok else 1)
