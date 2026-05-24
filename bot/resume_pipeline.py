"""Background resume processing (LLM, API calls) — runs in bot-worker only."""

import base64
import io
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from pypdf import PdfReader
from telegram import Bot
from telegram.ext import ContextTypes

from app.services.llm_service import extract_candidate_name_from_resume

logger = logging.getLogger(__name__)

_MSG_PROCESSING_ACK = (
    "Спасибо! 📄 Резюме получено.\n\n"
    "Сейчас анализируем данные — это займёт около минуты. "
    "Мы напишем вам, как только будем готовы продолжить ⏳"
)
_MSG_PROCESSING_BUSY = (
    "⏳ Резюме ещё обрабатывается. Подождите немного — скоро продолжим."
)
_MSG_PIPELINE_ERROR = (
    "К сожалению, не удалось обработать резюме. "
    "Попробуйте отправить PDF ещё раз или напишите текстом опыт работы."
)
_MSG_DOCX_STUB = (
    "Формат Word (.docx) пока в разработке 🙏\n\n"
    "Пожалуйста, отправьте резюме как PDF или текстом "
    "(можно вставить ссылку на hh.ru или кратко описать опыт)."
)


@dataclass
class ResumeInput:
    kind: str  # pdf | text
    resume_text: str | None = None
    file_bytes: bytes | None = None
    filename: str | None = None


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_pdf_avatar(file_bytes: bytes) -> tuple[bytes, str] | None:
    """
    Возвращает (file_bytes, ext) первой найденной картинки на первой странице.
    """
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        if not reader.pages:
            return None

        first_page = reader.pages[0]
        images = first_page.images
        if not images:
            return None

        best: tuple[bytes, str] | None = None
        best_size = 0
        for img_obj in images.values():
            data = img_obj.data
            if not data:
                continue
            ext = (
                img_obj.name.split(".")[-1].lower()
                if "." in img_obj.name
                else "jpg"
            )
            if ext not in ("jpg", "jpeg", "png", "webp"):
                ext = "jpg"
            if len(data) > best_size:
                best_size = len(data)
                best = (data, ext)
        return best
    except Exception as e:
        logger.warning("Failed to extract avatar from PDF: %s", e)
    return None


async def run_resume_pipeline(
    *,
    bot: Bot,
    chat_id: int,
    ctx: ContextTypes.DEFAULT_TYPE,
    agency_id: str,
    backend: str,
    headers: dict[str, str],
    resume_input: ResumeInput,
    api_post,
    load_questions,
    create_screening,
    complete_screening,
    cancel_reminder,
    create_reminder,
    first_question_message,
    next_question_message,
    final_message,
) -> None:
    """Process resume off the hot path; update ctx.user_data and message user."""
    ud = ctx.user_data
    telegram_id = str(chat_id)
    vacancy_id = ud.get("vacancy_id")
    vacancy_title = ud.get("vacancy_title", "")

    try:
        if resume_input.kind == "pdf":
            if not resume_input.file_bytes:
                raise ValueError("Missing PDF bytes")
            resume_text = extract_pdf_text(resume_input.file_bytes)
        else:
            resume_text = (resume_input.resume_text or "").strip()

        if not resume_text:
            await bot.send_message(
                chat_id,
                "Не удалось извлечь текст из резюме. "
                "Попробуйте другой PDF или отправьте текстом.",
            )
            return

        try:
            name_data = await extract_candidate_name_from_resume(resume_text)
        except Exception:
            logger.exception("LLM name extraction failed")
            name_data = {
                "first_name": "Кандидат",
                "last_name": "",
                "full_name": "Кандидат",
            }

        ud["first_name"] = name_data["first_name"]
        ud["full_name"] = name_data["full_name"]
        ud["resume_text"] = resume_text

        async with httpx.AsyncClient(timeout=120.0) as client:
            cand_response = await api_post(
                client,
                "/internal/candidates/",
                {
                    "full_name": name_data["full_name"],
                    "telegram_id": telegram_id,
                    "resume_text": resume_text,
                },
            )

        if cand_response.status_code not in (200, 201):
            logger.error(
                "Candidate create failed: %s %s",
                cand_response.status_code,
                cand_response.text,
            )
            await bot.send_message(chat_id, _MSG_PIPELINE_ERROR)
            return

        candidate_id = cand_response.json()["id"]
        ud["candidate_id"] = candidate_id

        if resume_input.kind == "pdf" and resume_input.file_bytes:
            file_b64 = base64.b64encode(resume_input.file_bytes).decode()
            async with httpx.AsyncClient(timeout=60.0) as client:
                upload_resp = await api_post(
                    client,
                    "/internal/candidates/upload-resume",
                    {
                        "candidate_id": candidate_id,
                        "file_base64": file_b64,
                        "filename": resume_input.filename or "resume.pdf",
                    },
                )
                if upload_resp.status_code not in (200, 201):
                    logger.warning(
                        "Resume upload failed: %s %s",
                        upload_resp.status_code,
                        upload_resp.text,
                    )

                avatar_data = extract_pdf_avatar(resume_input.file_bytes)
                if avatar_data:
                    img_bytes, ext = avatar_data
                    img_b64 = base64.b64encode(img_bytes).decode()
                    avatar_resp = await api_post(
                        client,
                        "/internal/candidates/upload-avatar",
                        {
                            "candidate_id": candidate_id,
                            "file_base64": img_b64,
                            "filename": f"avatar.{ext}",
                        },
                    )
                    if avatar_resp.status_code not in (200, 201):
                        logger.warning("Avatar upload failed: %s", avatar_resp.text)

        await cancel_reminder(telegram_id)

        questions = await load_questions(vacancy_id)
        ud["questions"] = questions
        ud["answers"] = []
        ud["question_index"] = 0

        if not questions:
            screening_id = await create_screening(
                vacancy_id, candidate_id, run_llm=True
            )
            if not screening_id:
                await bot.send_message(chat_id, _MSG_PIPELINE_ERROR)
                return
            ud["screening_id"] = screening_id
            name = ud.get("first_name", "Кандидат")
            days = ud.get("feedback_days", 3)
            await bot.send_message(
                chat_id, final_message(name, days, had_questions=False)
            )
            ud["awaiting_questions"] = False
            ud["conversation_finished"] = True
            return

        screening_id = await create_screening(
            vacancy_id, candidate_id, run_llm=False
        )
        if screening_id:
            ud["screening_id"] = screening_id
            await create_reminder(
                telegram_id=telegram_id,
                state="waiting_answers",
                vacancy_title=vacancy_title,
                screening_id=screening_id,
            )
        else:
            logger.warning("Screening id missing after resume pipeline")

        name = ud.get("first_name", "Кандидат")
        total = len(questions)
        text = first_question_message(name, total, questions[0]["text"])
        await bot.send_message(chat_id, text)

        ud["awaiting_questions"] = True
        ud["conversation_finished"] = False

    except Exception:
        logger.exception("Resume pipeline failed for chat_id=%s", chat_id)
        await bot.send_message(chat_id, _MSG_PIPELINE_ERROR)
    finally:
        ud["processing_resume"] = False


def schedule_resume_pipeline(
    *,
    bot: Bot,
    chat_id: int,
    ctx: ContextTypes.DEFAULT_TYPE,
    coro_factory,
) -> None:
    """Fire-and-forget background task on the bot event loop."""
    import asyncio

    async def _wrapper() -> None:
        try:
            await coro_factory()
        except Exception:
            logger.exception("Unhandled error in resume pipeline task")

    asyncio.create_task(_wrapper())
