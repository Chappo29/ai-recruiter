# Recruiter

Async SQLAlchemy + asyncpg with Alembic migrations.

## Prerequisites (Windows)

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (recommended), or a local PostgreSQL 15+ install
- Python 3.11+ and a virtual environment

You do **not** need `psql` on your PATH if you use Docker (see below).

## Quick start

From the project root (`recruiter`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 1. Start PostgreSQL (Docker)

```powershell
docker compose up -d
```

Wait until the container is healthy (`docker compose ps`). Default credentials:

| Setting  | Value      |
|----------|------------|
| Host     | localhost  |
| Port     | 5432       |
| Database | recruiter  |
| User     | postgres   |
| Password | postgres   |

### 2. Set `DATABASE_URL`

PowerShell (current session):

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/recruiter"
```

Or copy `.env.example` to `.env` and load it with your own tooling. **Do not commit** `.env`.

If your password contains `@`, `#`, spaces, Cyrillic, or other special characters, URL-encode **only the password**:

```python
from urllib.parse import quote_plus
password = quote_plus("your-password-here")
url = f"postgresql+asyncpg://postgres:{password}@localhost:5432/recruiter"
```

### 3. Check connection (optional)

```powershell
python scripts/check_db.py
```

### 4. Run migrations

```powershell
alembic upgrade head
```

### 5. Run API (FastAPI)

**Important:** use the project venv (folder `.venv`, not global `uvicorn`). Otherwise you may see `slowapi` / `email-validator is not installed`.

**Recommended (Windows):**

```powershell
.\run-api.ps1
```

Or manually:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/recruiter"
$env:SECRET_KEY = "dev-secret-change-in-production"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for interactive API docs.

Protected routes need `Authorization: Bearer <access_token>` from `POST /auth/login`.

### 6. Bot worker (Telegram polling)

API and bot polling run in **separate processes**. FastAPI can use multiple workers; the bot worker must be a **single** instance.

```powershell
# Terminal 2 — same .env / DATABASE_URL / SECRET_KEY / INTERNAL_API_KEY
.\run-bot.ps1
# or: .\.venv\Scripts\python.exe -m bot
```

Control API: http://127.0.0.1:8001/health  
Start/stop bots from the web panel (`POST /bots/start`) calls this worker.

Outbound messages (reject, reminders) use the Telegram HTTP API with the token from the database — they work from any API worker without polling.

### 7. Inspect tables without local `psql`

**Docker exec:**

```powershell
docker exec -it recruiter-db psql -U postgres -d recruiter -c "\dt"
```

List tables in the `public` schema:

```powershell
docker exec -it recruiter-db psql -U postgres -d recruiter -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
```

**GUI:** [pgAdmin](https://www.pgadmin.org/download/) — connect to `localhost:5432` with the credentials above.

## Troubleshooting

| Error | Fix |
|-------|-----|
| `ConnectionRefusedError` / WinError 1225 on port 5432 | Run `docker compose up -d` or start local PostgreSQL |
| `psql` not recognized | Use `docker exec` above or install PostgreSQL client tools |
| `email-validator is not installed` / `No module named 'slowapi'` | Use `.\run-api.ps1` or `.\.venv\Scripts\python.exe -m uvicorn ...` (not global `uvicorn`) |
| `venv\Scripts\activate` not found | Folder is `.venv` — run `.\.venv\Scripts\Activate.ps1` |
| `lxml` build failed on Python 3.13 | Use `lxml>=5.3` from requirements (prebuilt wheel); parser falls back to `html.parser` if lxml missing |
| Auth / connection string errors with special password | URL-encode password with `urllib.parse.quote_plus` |
| `Bot worker unavailable` on start/stop | Run `python -m bot` in a second terminal |
| Reminders not sent | Set `telegram_bot_token` in DB; token is loaded per `agency_id` |

Stop database:

```powershell
docker compose down
```

Remove data volume (destructive):

```powershell
docker compose down -v
```
