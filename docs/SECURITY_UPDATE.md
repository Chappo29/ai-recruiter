# Обновление безопасности и RBAC — Инструкция по миграции

## 🎯 Что изменилось

### ✅ Исправлены уязвимости безопасности

1. **Ограничение размера файлов**
   - PDF резюме: максимум 10 MB (настраивается через `MAX_RESUME_SIZE_MB`)
   - Аватары: максимум 5 MB (настраивается через `MAX_AVATAR_SIZE_MB`)

2. **Проверка MIME-типов**
   - PDF файлы проверяются по magic numbers (не только по расширению)
   - Изображения проверяются на валидный формат (JPEG/PNG/WebP)
   - Защита от загрузки замаскированных исполняемых файлов

3. **Усиленная валидация секретов**
   - `SECRET_KEY` и `INTERNAL_API_KEY` теперь должны быть минимум 32 символа
   - При старте приложения выдается ошибка, если секреты слишком короткие

### ✅ Реализована система ролей (RBAC)

**Роли:**
- `admin` — полный доступ ко всем операциям, включая управление ботом и удаление вакансий
- `recruiter` — стандартный доступ (создание вакансий, просмотр кандидатов, скрининги)

**Иерархия:**
- При регистрации нового агентства первый пользователь автоматически получает роль `admin`
- Последующие пользователи в агентстве получают роль `recruiter` (в будущем admin сможет приглашать)

**Защищенные операции:**
- `POST /bots/start` — только admin
- `POST /bots/stop` — только admin
- `DELETE /vacancies/{id}` — только admin

### ✅ Убран хардкод

Все константы вынесены в конфигурацию (`app/core/config.py`) и читаются из переменных окружения:

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `MAX_RESUME_SIZE_MB` | 10 | Максимальный размер PDF резюме (MB) |
| `MAX_AVATAR_SIZE_MB` | 5 | Максимальный размер аватара (MB) |
| `OLLAMA_URL` | http://localhost:11434/api/generate | URL Ollama API |
| `OLLAMA_MODEL` | qwen2.5:7b-instruct | Модель LLM |
| `OLLAMA_TIMEOUT_SEC` | 300 | Таймаут запросов к LLM (сек) |
| `DEFAULT_FEEDBACK_DAYS` | 3 | Количество дней до напоминания |
| `BACKEND_URL` | http://localhost:8000 | URL бэкенда для бота |
| `BOT_WORKER_URL` | http://127.0.0.1:8001 | URL control API бота |

---

## 🚀 Инструкция по обновлению

### Шаг 1: Обновите .env файл

Добавьте новые переменные в ваш `.env` файл (смотрите `.env.example`):

```bash
# CRITICAL: Минимум 32 символа! Сгенерируйте новые ключи:
# Windows PowerShell:
# [Convert]::ToBase64String((1..32 | ForEach-Object {Get-Random -Max 256}))
# Linux/Mac:
# openssl rand -hex 32

SECRET_KEY=ваш-существующий-ключ-или-новый-32+символов
INTERNAL_API_KEY=ваш-существующий-ключ-или-новый-32+символов

# Новые настройки (опционально, если нужны не дефолтные):
MAX_RESUME_SIZE_MB=10
MAX_AVATAR_SIZE_MB=5
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_TIMEOUT_SEC=300
DEFAULT_FEEDBACK_DAYS=3
```

**ВАЖНО:** Если ваши существующие `SECRET_KEY` или `INTERNAL_API_KEY` короче 32 символов, приложение **не запустится**. Сгенерируйте новые ключи.

### Шаг 2: Примените миграцию базы данных

```powershell
# Активируйте виртуальное окружение
.\.venv\Scripts\Activate.ps1

# Примените миграцию
alembic upgrade head
```

Миграция автоматически:
- Установит роль `admin` первому пользователю в каждом агентстве
- Установит роль `recruiter` всем остальным пользователям
- Добавит constraint для валидации ролей

### Шаг 3: Перезапустите приложение

```powershell
# Terminal 1 — API
.\run-api.ps1

# Terminal 2 — Bot worker
.\run-bot.ps1
```

При старте приложение проверит:
- Длину `SECRET_KEY` и `INTERNAL_API_KEY` (минимум 32 символа)
- Если проверка не пройдёт, вы увидите ошибку с инструкцией

---

## 🔐 Проверка безопасности

### Проверьте роли пользователей

```sql
-- Подключитесь к базе данных
docker exec -it recruiter-db psql -U postgres -d recruiter

-- Посмотрите роли пользователей
SELECT u.email, u.role, a.name as agency 
FROM users u 
JOIN agencies a ON u.agency_id = a.id 
ORDER BY a.name, u.created_at;
```

Ожидаемый результат:
- Первый пользователь каждого агентства должен иметь роль `admin`
- Остальные — `recruiter`

### Проверьте работу RBAC

1. **Войдите как recruiter** (не первый пользователь агентства):
   ```bash
   curl -X POST http://localhost:8000/bots/start \
     -H "Authorization: Bearer <recruiter_token>" \
     -H "Content-Type: application/json" \
     -d '{"token": "..."}'
   ```
   
   **Ожидается:** `403 Forbidden` с сообщением `Требуется роль 'admin' или выше`

2. **Войдите как admin** (первый пользователь):
   ```bash
   curl -X POST http://localhost:8000/bots/start \
     -H "Authorization: Bearer <admin_token>" \
     -H "Content-Type: application/json" \
     -d '{"token": "..."}'
   ```
   
   **Ожидается:** `200 OK` и бот запущен

### Проверьте ограничения файлов

Попробуйте загрузить файл больше 10 MB:

**Ожидается:** `413 Request Entity Too Large` с сообщением `File too large. Maximum size: 10 MB`

---

## 📋 Список изменённых файлов

### Новые файлы:
- `app/core/rbac.py` — система ролей и декораторы
- `app/utils/file_validation.py` — валидация файлов с MIME-типами
- `alembic/versions/9b8c74d3e5a1_update_user_roles_with_rbac.py` — миграция ролей

### Изменённые файлы:
- `app/core/config.py` — все настройки вынесены в конфигурацию
- `app/routers/auth.py` — использование `UserRole` enum, первый пользователь = admin
- `app/routers/bots.py` — защита управления ботом декораторами `@require_role`
- `app/routers/vacancies.py` — защита удаления вакансий, валидация PDF файлов
- `app/routers/candidates.py` — валидация изображений при загрузке
- `app/services/llm_service.py` — использование конфига вместо хардкода
- `app/schemas/user.py` — валидация ролей через Pydantic
- `app/main.py` — использование `BOT_WORKER_URL` из конфига
- `bot/handlers.py` — использование `DEFAULT_FEEDBACK_DAYS` из конфига
- `bot/worker_control.py` — использование `BACKEND_URL` из конфига
- `.env.example` — добавлены все новые переменные окружения

---

## 🎓 Как использовать RBAC в новых endpoint'ах

### Пример защиты endpoint'а:

```python
from app.core.rbac import UserRole, require_role
from app.deps import CurrentUser

@router.post("/admin-only-action")
@require_role(UserRole.ADMIN)
async def admin_only_action(
    current_user: CurrentUser,
    db: DbSession,
):
    # Этот endpoint доступен только admin'ам
    return {"status": "ok"}
```

### Программная проверка роли:

```python
from app.core.rbac import has_role, is_admin, UserRole

# В функции
if not has_role(current_user, UserRole.ADMIN):
    raise HTTPException(status_code=403, detail="Admin required")

# Или короче:
if not is_admin(current_user):
    raise HTTPException(status_code=403, detail="Admin required")
```

---

## ⚠️ Breaking Changes

### Для разработчиков:

1. **SECRET_KEY и INTERNAL_API_KEY теперь должны быть минимум 32 символа**
   - Если ваши ключи короче, приложение не запустится
   - Сгенерируйте новые: `openssl rand -hex 32`

2. **Роли пользователей изменились**
   - Старая роль `"admin"` (строка) → `UserRole.ADMIN` (enum)
   - При создании пользователя используйте `UserRole.ADMIN.value` или `UserRole.RECRUITER.value`

3. **Импорты изменились**
   - Если вы импортировали `OLLAMA_URL`, `BACKEND_URL` и т.д. из модулей — обновите на импорт из `app.core.config`

### Для пользователей:

1. **Recruiter'ы больше не могут управлять ботом**
   - Только admin (первый пользователь агентства) может запускать/останавливать бота

2. **Recruiter'ы не могут удалять вакансии**
   - Только admin может удалять вакансии
   - Архивация доступна всем (как раньше)

---

## 🐛 Rollback (откат изменений)

Если что-то пошло не так:

```powershell
# Откат миграции базы данных
alembic downgrade -1

# Откат кода
git revert HEAD
```

**Примечание:** При откате миграции все пользователи получат роль `admin` (для безопасности).

---

## 📞 Поддержка

Если возникли проблемы:
1. Проверьте логи приложения
2. Проверьте, что все переменные в `.env` установлены корректно
3. Проверьте, что миграция применилась: `alembic current`
4. Проверьте роли пользователей в БД (SQL выше)
