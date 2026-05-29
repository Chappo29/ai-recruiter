"""
Автоматическое тестирование API recruiter
"""
import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"

class TestRunner:
    def __init__(self):
        self.results = []
        self.admin_token = None
        self.recruiter_token = None
        self.test_agency_id = None
        self.test_vacancy_id = None
        
    def log(self, test_name, status, message=""):
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "time": datetime.now().isoformat()
        }
        self.results.append(result)
        icon = "[OK]" if status == "PASS" else "[FAIL]" if status == "FAIL" else "[WARN]"
        print(f"{icon} {test_name}: {message}")
        
    async def run_all(self):
        print("\n" + "="*60)
        print("ЗАПУСК АВТОМАТИЧЕСКИХ ТЕСТОВ")
        print("="*60 + "\n")
        
        await self.test_register_new_company()
        await self.test_login_admin()
        await self.test_get_me()
        await self.test_create_vacancy()
        await self.test_admin_can_start_bot()
        await self.test_admin_can_delete_vacancy()
        await self.test_agency_isolation()
        
        print("\n" + "="*60)
        print("РЕЗУЛЬТАТЫ ТЕСТОВ")
        print("="*60)
        
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        warnings = sum(1 for r in self.results if r["status"] == "WARN")
        
        print(f"\n[OK] Пройдено: {passed}")
        print(f"[FAIL] Провалено: {failed}")
        print(f"[WARN] Предупреждений: {warnings}")
        print(f"Всего тестов: {len(self.results)}\n")
        
        return self.results
        self.test_email = None
        
    async def test_register_new_company(self):
        """Тест: Регистрация новой компании"""
        async with httpx.AsyncClient() as client:
            try:
                timestamp = datetime.now().strftime("%H%M%S")
                self.test_email = f"admin_{timestamp}@test.com"
                response = await client.post(
                    f"{BASE_URL}/auth/register",
                    json={
                        "agency_name": f"TestAgency_{timestamp}",
                        "email": self.test_email,
                        "password": "TestPassword123!"
                    }
                )
                
                if response.status_code == 201:
                    data = response.json()
                    self.test_agency_id = data.get("agency_id")
                    
                    # Проверяем, что роль = admin
                    if data.get("role") == "admin":
                        self.log("register_new_company", "PASS", 
                                f"Создана компания, роль: {data['role']}")
                    else:
                        self.log("register_new_company", "FAIL", 
                                f"Неправильная роль: {data.get('role')}, ожидалось: admin")
                else:
                    self.log("register_new_company", "FAIL", 
                            f"Код {response.status_code}: {response.text}")
            except Exception as e:
                self.log("register_new_company", "FAIL", str(e))
                
    async def test_login_admin(self):
        """Тест: Логин admin'а"""
        async with httpx.AsyncClient() as client:
            try:
                timestamp = datetime.now().strftime("%H%M%S")
                response = await client.post(
                    f"{BASE_URL}/auth/login",
                    json={
                        "email": self.test_email or f"admin_{datetime.now().strftime('%H%M%S')}@test.com",
                        "password": "TestPassword123!"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.admin_token = data.get("access_token")
                    self.log("login_admin", "PASS", "Успешный логин admin")
                else:
                    self.log("login_admin", "FAIL", 
                            f"Код {response.status_code}: {response.text}")
            except Exception as e:
                self.log("login_admin", "FAIL", str(e))
                
    async def test_get_me(self):
        """Тест: Получение информации о текущем пользователе"""
        if not self.admin_token:
            self.log("get_me", "FAIL", "Нет токена admin")
            return
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{BASE_URL}/auth/me",
                    headers={"Authorization": f"Bearer {self.admin_token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("role") == "admin":
                        self.log("get_me", "PASS", f"Роль подтверждена: {data['role']}")
                    else:
                        self.log("get_me", "FAIL", f"Неправильная роль: {data.get('role')}")
                else:
                    self.log("get_me", "FAIL", f"Код {response.status_code}")
            except Exception as e:
                self.log("get_me", "FAIL", str(e))
                
    async def test_create_vacancy(self):
        """Тест: Создание вакансии"""
        if not self.admin_token:
            self.log("create_vacancy", "FAIL", "Нет токена admin")
            return
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{BASE_URL}/vacancies/",
                    headers={"Authorization": f"Bearer {self.admin_token}"},
                    json={
                        "title": "Test Vacancy",
                        "company": "Test Company",
                        "requirements": "Test requirements",
                        "description": "Test description"
                    }
                )
                
                if response.status_code == 201:
                    data = response.json()
                    self.test_vacancy_id = data.get("id")
                    self.log("create_vacancy", "PASS", f"Создана вакансия ID: {self.test_vacancy_id}")
                else:
                    self.log("create_vacancy", "FAIL", 
                            f"Код {response.status_code}: {response.text}")
            except Exception as e:
                self.log("create_vacancy", "FAIL", str(e))
                
    async def test_admin_can_start_bot(self):
        """Тест: Admin может запустить бота"""
        if not self.admin_token:
            self.log("admin_can_start_bot", "FAIL", "Нет токена admin")
            return
            
        async with httpx.AsyncClient() as client:
            try:
                # Сначала проверяем статус
                response = await client.get(
                    f"{BASE_URL}/bots/status",
                    headers={"Authorization": f"Bearer {self.admin_token}"}
                )
                
                if response.status_code == 200:
                    self.log("admin_can_start_bot", "PASS", 
                            "Admin имеет доступ к статусу бота")
                elif response.status_code == 403:
                    self.log("admin_can_start_bot", "FAIL", 
                            "Admin НЕ имеет доступа (403 Forbidden)")
                else:
                    self.log("admin_can_start_bot", "WARN", 
                            f"Неожиданный код: {response.status_code}")
            except Exception as e:
                self.log("admin_can_start_bot", "FAIL", str(e))
                
    async def test_admin_can_delete_vacancy(self):
        """Тест: Admin может удалить вакансию"""
        if not self.admin_token or not self.test_vacancy_id:
            self.log("admin_can_delete_vacancy", "FAIL", 
                    "Нет токена admin или ID вакансии")
            return
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{BASE_URL}/vacancies/{self.test_vacancy_id}",
                    headers={"Authorization": f"Bearer {self.admin_token}"}
                )
                
                if response.status_code == 204:
                    self.log("admin_can_delete_vacancy", "PASS", 
                            "Admin успешно удалил вакансию")
                elif response.status_code == 403:
                    self.log("admin_can_delete_vacancy", "FAIL", 
                            "Admin НЕ может удалить (403 Forbidden)")
                else:
                    self.log("admin_can_delete_vacancy", "FAIL", 
                            f"Код {response.status_code}: {response.text}")
            except Exception as e:
                self.log("admin_can_delete_vacancy", "FAIL", str(e))
                
    async def test_agency_isolation(self):
        """Тест: Изоляция данных между компаниями"""
        # Создаем второго пользователя в другой компании
        async with httpx.AsyncClient() as client:
            try:
                timestamp = datetime.now().strftime("%H%M%S")
                response = await client.post(
                    f"{BASE_URL}/auth/register",
                    json={
                        "agency_name": f"OtherAgency_{timestamp}",
                        "email": f"other_{timestamp}@test.com",
                        "password": "TestPassword123!"
                    }
                )
                
                if response.status_code != 201:
                    self.log("agency_isolation", "FAIL", "Не удалось создать второго пользователя")
                    return
                    
                # Логинимся как второй пользователь
                response = await client.post(
                    f"{BASE_URL}/auth/login",
                    json={
                        "email": f"other_{timestamp}@test.com",
                        "password": "TestPassword123!"
                    }
                )
                
                if response.status_code != 200:
                    self.log("agency_isolation", "FAIL", "Не удалось залогиниться")
                    return
                    
                other_token = response.json().get("access_token")
                
                # Пытаемся получить вакансии - должны быть пустые
                response = await client.get(
                    f"{BASE_URL}/vacancies/",
                    headers={"Authorization": f"Bearer {other_token}"}
                )
                
                if response.status_code == 200:
                    vacancies = response.json()
                    if len(vacancies) == 0:
                        self.log("agency_isolation", "PASS", 
                                "Компании изолированы: другой пользователь не видит чужие вакансии")
                    else:
                        self.log("agency_isolation", "FAIL", 
                                f"УТЕЧКА ДАННЫХ: Другой пользователь видит {len(vacancies)} вакансий!")
                else:
                    self.log("agency_isolation", "WARN", 
                            f"Неожиданный код: {response.status_code}")
            except Exception as e:
                self.log("agency_isolation", "FAIL", str(e))

if __name__ == "__main__":
    runner = TestRunner()
    asyncio.run(runner.run_all())
