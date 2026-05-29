"""Shared Ollama client with retries, validation, and structured logging."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import (
    LLM_MAX_RETRIES,
    LLM_PROMPT_VERSION,
    OLLAMA_MODEL,
    OLLAMA_SEED,
    OLLAMA_TEMPERATURE,
    OLLAMA_TIMEOUT_SEC,
    OLLAMA_TOP_P,
    OLLAMA_URL,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClientError(Exception):
    """Raised when all LLM retries are exhausted."""


def _parse_json_raw(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        clean = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)


async def generate_json(
    prompt: str,
    *,
    schema: type[T] | None = None,
    max_retries: int | None = None,
) -> dict[str, Any] | T:
    """Call Ollama with JSON format, retry on parse/validation errors."""
    retries = max_retries if max_retries is not None else LLM_MAX_RETRIES
    last_error: Exception | None = None

    has_schema = schema is not None
    payload: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": OLLAMA_TEMPERATURE,
            "top_p": OLLAMA_TOP_P,
        },
    }
    if OLLAMA_SEED is not None:
        payload["options"]["seed"] = OLLAMA_SEED

    for attempt in range(1, retries + 1):
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=float(OLLAMA_TIMEOUT_SEC)) as client:
                response = await client.post(OLLAMA_URL, json=payload)
                response.raise_for_status()
                raw = response.json()["response"].strip()

            data = _parse_json_raw(raw)
            latency_ms = int((time.perf_counter() - started) * 1000)

            if schema is not None:
                validated = schema.model_validate(data)
                logger.info(
                    "llm_call ok model=%s prompt_version=%s attempt=%s latency_ms=%s schema=%s",
                    OLLAMA_MODEL,
                    LLM_PROMPT_VERSION,
                    attempt,
                    latency_ms,
                    has_schema,
                )
                return validated

            logger.info(
                "llm_call ok model=%s prompt_version=%s attempt=%s latency_ms=%s schema=%s",
                OLLAMA_MODEL,
                LLM_PROMPT_VERSION,
                attempt,
                latency_ms,
                has_schema,
            )
            return data

        except (json.JSONDecodeError, ValidationError, httpx.HTTPError, KeyError) as exc:
            last_error = exc
            latency_ms = int((time.perf_counter() - started) * 1000)
            logger.warning(
                "llm_call retry model=%s prompt_version=%s attempt=%s/%s "
                "latency_ms=%s schema=%s error=%s",
                OLLAMA_MODEL,
                LLM_PROMPT_VERSION,
                attempt,
                retries,
                latency_ms,
                has_schema,
                type(exc).__name__,
            )
            if attempt < retries:
                await asyncio.sleep(2 ** (attempt - 1))

    logger.error(
        "llm_call failed model=%s prompt_version=%s retries=%s schema=%s error=%s",
        OLLAMA_MODEL,
        LLM_PROMPT_VERSION,
        retries,
        has_schema,
        last_error,
    )
    raise LLMClientError(str(last_error)) from last_error
