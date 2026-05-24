"""Test DATABASE_URL connectivity (async SQLAlchemy + asyncpg)."""

import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DEFAULT_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/recruiter"


async def main() -> int:
    url = os.getenv("DATABASE_URL", DEFAULT_URL)
    engine = create_async_engine(url, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except ConnectionRefusedError:
        print(
            "Connection refused on localhost:5432.\n"
            "Start PostgreSQL: docker compose up -d\n"
            "Then set DATABASE_URL (see .env.example) and retry.",
            file=sys.stderr,
        )
        return 1
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1225 or "refused" in str(exc).lower():
            print(
                "Cannot reach PostgreSQL (connection refused).\n"
                "Start PostgreSQL: docker compose up -d",
                file=sys.stderr,
            )
            return 1
        raise
    finally:
        await engine.dispose()

    print("Database connection OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
