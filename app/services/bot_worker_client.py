"""HTTP client for the dedicated bot-worker control plane."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

BOT_WORKER_URL = os.getenv("BOT_WORKER_URL", "http://127.0.0.1:8001").rstrip("/")
INTERNAL_KEY = os.getenv("INTERNAL_API_KEY", "")


class BotWorkerError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not INTERNAL_KEY:
        raise BotWorkerError("INTERNAL_API_KEY is not set")
    return {"X-Internal-Key": INTERNAL_KEY}


async def start_bot(agency_id: str, token: str, backend_url: str) -> None:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BOT_WORKER_URL}/control/start",
            headers=_headers(),
            json={
                "agency_id": agency_id,
                "token": token,
                "backend_url": backend_url,
            },
        )
    if response.status_code >= 400:
        detail = response.text
        try:
            detail = response.json().get("detail", detail)
        except Exception:
            pass
        raise BotWorkerError(detail or f"Worker returned {response.status_code}")


async def stop_bot(agency_id: str) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BOT_WORKER_URL}/control/stop",
            headers=_headers(),
            json={"agency_id": agency_id},
        )
    if response.status_code >= 400:
        raise BotWorkerError(response.text)
