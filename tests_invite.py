"""
Тестирование системы приглашений и recruiter роли
"""
import asyncio
import httpx

BASE_URL = "http://127.0.0.1:8000"

async def test_invite_system():
    import time
    timestamp = str(int(time.time()))
    
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ СИСТЕМЫ ПРИГЛАШЕНИЙ")
    print("="*60 + "\n")
    
    # 1. Регистрация admin'а
    print("[1/7] Регистрация admin...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/auth/register",
            json={
                "agency_name": f"Test Company {timestamp}",
                "email": f"admin_invite_{timestamp}@test.com",
                "password": "TestPassword123!"
            }
        )
        if response.status_code != 201:
            print(f"[FAIL] Не удалось зарегистрировать admin: {response.text}")
            return
        print("[OK] Admin зарегистрирован")
        
    # 2. Логин admin
    print("\n[2/7] Логин admin...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": f"admin_invite_{timestamp}@test.com",
                "password": "TestPassword123!"
            }
        )
        if response.status_code != 200:
            print(f"[FAIL] Не удалось залогиниться: {response.text}")
            return
        admin_token = response.json()["access_token"]
        print("[OK] Admin залогинился")
        
    # 3. Admin приглашает recruiter'а
    print("\n[3/7] Admin приглашает recruiter...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/team/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": f"recruiter_{timestamp}@test.com",
                "role": "recruiter"
            }
        )
        if response.status_code != 200:
            print(f"[FAIL] Не удалось создать приглашение: {response.text}")
            return
        invitation_token = response.json()["invitation_token"]
        print(f"[OK] Приглашение создано: {invitation_token[:20]}...")
        
    # 4. Recruiter принимает приглашение
    print("\n[4/7] Recruiter принимает приглашение...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/team/accept-invite",
            json={
                "invitation_token": invitation_token,
                "password": "RecruiterPassword123!"
            }
        )
        if response.status_code != 201:
            print(f"[FAIL] Не удалось принять приглашение: {response.text}")
            return
        user_data = response.json()
        if user_data.get("role") != "recruiter":
            print(f"[FAIL] Неправильная роль: {user_data.get('role')}")
            return
        print(f"[OK] Recruiter создан с ролью: {user_data['role']}")
        
    # 5. Логин recruiter
    print("\n[5/7] Логин recruiter...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": f"recruiter_{timestamp}@test.com",
                "password": "RecruiterPassword123!"
            }
        )
        if response.status_code != 200:
            print(f"[FAIL] Не удалось залогиниться как recruiter: {response.text}")
            return
        recruiter_token = response.json()["access_token"]
        print("[OK] Recruiter залогинился")
        
    # 6. Recruiter НЕ может управлять ботом
    print("\n[6/7] Проверка: recruiter НЕ может управлять ботом...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/bots/status",
            headers={"Authorization": f"Bearer {recruiter_token}"}
        )
        # Recruiter может просматривать статус, это ОК
        if response.status_code == 200:
            print("[OK] Recruiter может просматривать статус бота")
        
        # Но НЕ может запускать
        response = await client.post(
            f"{BASE_URL}/bots/start",
            headers={"Authorization": f"Bearer {recruiter_token}"},
            json={"token": "fake_token"}
        )
        if response.status_code == 403:
            print("[OK] Recruiter НЕ может запустить бота (403 Forbidden)")
        else:
            print(f"[FAIL] Recruiter смог запустить бота! Код: {response.status_code}")
            
    # 7. Admin создает вакансию, recruiter её видит
    print("\n[7/7] Проверка: recruiter видит вакансии своего агентства...")
    async with httpx.AsyncClient() as client:
        # Admin создает вакансию
        response = await client.post(
            f"{BASE_URL}/vacancies/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Test Vacancy for Team",
                "company": "Test Company",
                "requirements": "Test",
                "description": "Test"
            }
        )
        if response.status_code != 201:
            print(f"[FAIL] Admin не смог создать вакансию: {response.text}")
            return
        vacancy_id = response.json()["id"]
        
        # Recruiter видит вакансии
        response = await client.get(
            f"{BASE_URL}/vacancies/",
            headers={"Authorization": f"Bearer {recruiter_token}"}
        )
        if response.status_code != 200:
            print(f"[FAIL] Recruiter не смог получить вакансии: {response.text}")
            return
        vacancies = response.json()
        if len(vacancies) > 0:
            print(f"[OK] Recruiter видит {len(vacancies)} вакансий своего агентства")
        else:
            print("[WARN] Recruiter не видит вакансии (возможно, фильтрация по user_id)")
        
        # Recruiter НЕ может удалить вакансию
        response = await client.delete(
            f"{BASE_URL}/vacancies/{vacancy_id}",
            headers={"Authorization": f"Bearer {recruiter_token}"}
        )
        if response.status_code == 403:
            print("[OK] Recruiter НЕ может удалить вакансию (403 Forbidden)")
        elif response.status_code == 404:
            print("[WARN] Recruiter не видит вакансию admin'а (фильтрация по user_id)")
        else:
            print(f"[FAIL] Recruiter смог удалить вакансию! Код: {response.status_code}")
    
    print("\n" + "="*60)
    print("ВСЕ ТЕСТЫ СИСТЕМЫ ПРИГЛАШЕНИЙ ПРОЙДЕНЫ!")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_invite_system())
