"""Background resume processing (LLM, API calls) — runs in bot-worker only."""

import base64
import io
import logging
from dataclasses import dataclass

import httpx
from pypdf import PdfReader
from telegram import Bot
from telegram.ext import ContextTypes

from app.services.llm_service import (
    extract_candidate_name_from_resume,
    fallback_interview_question,
    run_bot_interview_turn,
)
from app.utils.name import parse_candidate_names

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
_MAX_INTERVIEW_TURNS = 5


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
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        if not reader.pages:
            return None
        images = reader.pages[0].images
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


async def _append_dialog(api_post, screening_id: str, messages: list[dict]) -> None:
    async with httpx.AsyncClient(timeout=60.0) as client:
        await api_post(
            client,
            f"/internal/screenings/{screening_id}/dialog",
            {"messages": messages},
        )


async def run_resume_pipeline(
    *,
    bot: Bot,
    chat_id: int,
    ctx: ContextTypes.DEFAULT_TYPE,
    agency_id: str,
    resume_input: ResumeInput,
    api_post,
    create_screening,
    cancel_reminder,
    create_reminder,
    final_message,
) -> None:
    ud = ctx.user_data
    telegram_id = str(chat_id)
    vacancy_id = ud.get("vacancy_id")
    vacancy_title = ud.get("vacancy_title", "")
    vacancy_company = ud.get("vacancy_company") or "Компания"
    ai_prompt = ud.get("ai_screening_prompt")
    vacancy_text = ud.get("vacancy_text") or vacancy_title

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
            name_data = parse_candidate_names(resume_text)

        names = parse_candidate_names(
            resume_text,
            llm_full_name=name_data.get("full_name"),
            llm_first_name=name_data.get("first_name"),
        )
        ud["first_name"] = names["first_name"]
        ud["full_name"] = names["full_name"]
        ud["resume_text"] = resume_text
        first_name = names["first_name"]

        async with httpx.AsyncClient(timeout=120.0) as client:
            cand_response = await api_post(
                client,
                "/internal/candidates/",
                {
                    "full_name": ud["full_name"],
                    "first_name": ud["first_name"],
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
                    logger.warning("Resume upload failed: %s", upload_resp.text)

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

        screening_id = await create_screening(vacancy_id, candidate_id, run_llm=True)
        if not screening_id:
            await bot.send_message(chat_id, _MSG_PIPELINE_ERROR)
            return

        ud["screening_id"] = screening_id
        ud["dialog"] = []
        ud["interview_turns"] = 0

        use_ai_chat = bool((ai_prompt or "").strip()) or True

        if use_ai_chat:
            try:
                turn = await run_bot_interview_turn(
                    vacancy_title=vacancy_title,
                    company=vacancy_company,
                    vacancy_text=vacancy_text,
                    ai_screening_prompt=ai_prompt,
                    resume_text=resume_text,
                    dialog=[],
                    candidate_message=None,
                    candidate_first_name=first_name,
                )
            except Exception:
                logger.exception("Bot interview start failed")
                turn = {
                    "message": fallback_interview_question(
                        ai_prompt, first_name=first_name
                    ),
                    "done": False,
                }

            bot_msg = turn.get("message", "")
            await bot.send_message(chat_id, bot_msg)
            await _append_dialog(
                api_post,
                screening_id,
                [{"role": "assistant", "content": bot_msg}],
            )
            ud["dialog"] = [{"role": "assistant", "content": bot_msg}]
            ud["interview_turns"] = 1

            if turn.get("done"):
                days = ud.get("feedback_days", 3)
                await bot.send_message(
                    chat_id, final_message(first_name, days, had_questions=True)
                )
                ud["awaiting_questions"] = False
                ud["conversation_finished"] = True
            else:
                await create_reminder(
                    telegram_id=telegram_id,
                    state="waiting_answers",
                    vacancy_title=vacancy_title,
                    screening_id=screening_id,
                )
                ud["awaiting_questions"] = True
                ud["conversation_finished"] = False
        else:
            name = ud.get("first_name", "Кандидат")
            days = ud.get("feedback_days", 3)
            await bot.send_message(
                chat_id, final_message(name, days, had_questions=False)
            )
            ud["awaiting_questions"] = False
            ud["conversation_finished"] = True

    except Exception:
        logger.exception("Resume pipeline failed for chat_id=%s", chat_id)
        await bot.send_message(chat_id, _MSG_PIPELINE_ERROR)
    finally:
        ud["processing_resume"] = False


async def run_interview_reply(
    *,
    bot: Bot,
    chat_id: int,
    ctx: ContextTypes.DEFAULT_TYPE,
    user_text: str,
    api_post,
    final_message,
) -> bool:
    """Handle one candidate reply in AI interview. Returns True if conversation ended."""
    ud = ctx.user_data
    screening_id = ud.get("screening_id")
    if not screening_id:
        return True

    ud.setdefault("dialog", []).append({"role": "candidate", "content": user_text})
    await _append_dialog(
        api_post, screening_id, [{"role": "candidate", "content": user_text}]
    )

    turns = int(ud.get("interview_turns") or 0) + 1
    ud["interview_turns"] = turns

    try:
        turn = await run_bot_interview_turn(
            vacancy_title=ud.get("vacancy_title", ""),
            company=ud.get("vacancy_company") or "Компания",
            vacancy_text=ud.get("vacancy_text") or "",
            ai_screening_prompt=ud.get("ai_screening_prompt"),
            resume_text=ud.get("resume_text") or "",
            dialog=ud.get("dialog", []),
            candidate_message=user_text,
            candidate_first_name=ud.get("first_name", "коллега"),
        )
    except Exception:
        logger.exception("Bot interview turn failed")
        turn = {"message": "Спасибо за ответ! Передаю информацию рекрутеру.", "done": True}

    assistant_count = sum(
        1 for e in ud.get("dialog", []) if (e.get("role") or "").lower() == "assistant"
    )
    min_q = 3 if (ud.get("ai_screening_prompt") or "").strip() else 2
    llm_done = bool(turn.get("done"))
    if llm_done and (assistant_count + 1) < min_q:
        llm_done = False

    done = llm_done or turns >= _MAX_INTERVIEW_TURNS
    bot_msg = turn.get("message", "")
    if bot_msg:
        await bot.send_message(chat_id, bot_msg)
        ud["dialog"].append({"role": "assistant", "content": bot_msg})
        await _append_dialog(
            api_post, screening_id, [{"role": "assistant", "content": bot_msg}]
        )

    if done:
        name = ud.get("first_name", "Кандидат")
        days = ud.get("feedback_days", 3)
        await bot.send_message(chat_id, final_message(name, days, had_questions=True))
        ud["awaiting_questions"] = False
        ud["conversation_finished"] = True
        return True

    return False


def schedule_resume_pipeline(
    *,
    bot: Bot,
    chat_id: int,
    ctx: ContextTypes.DEFAULT_TYPE,
    coro_factory,
) -> None:
    import asyncio

    async def _wrapper() -> None:
        try:
            await coro_factory()
        except Exception:
            logger.exception("Unhandled error in resume pipeline task")

    asyncio.create_task(_wrapper())
