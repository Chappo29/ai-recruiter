"""Background resume processing (LLM, API calls) — runs in bot-worker only."""

import asyncio
import base64
import io
import logging
from dataclasses import dataclass

import httpx
from pypdf import PdfReader
from telegram import Bot
from telegram.ext import ContextTypes

from app.services.llm_service import classify_document, extract_candidate_name_from_resume
from bot.interview_runner import (
    finalize_screening,
    handle_structured_answer,
    start_structured_interview,
    use_structured_mode,
)
from app.core.config import MAX_RESUME_SIZE_MB
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
_MSG_NOT_A_RESUME = (
    "Кажется, это не резюме 🤔\n\n"
    "Пожалуйста, отправьте PDF-файл с вашим резюме — с ФИО, контактами и "
    "опытом работы (компания, должность, период работы).\n\n"
    "Как скачать с hh.ru:\n"
    "1. Зайдите на hh.ru → Моё резюме\n"
    "2. Нажмите «Скачать» → PDF\n"
    "3. Отправьте файл сюда"
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


def extract_pdf_text(file_bytes: bytes, *, max_pages: int | None = None) -> str:
    from app.core.config import MAX_PDF_PAGES

    limit = max_pages if max_pages is not None else MAX_PDF_PAGES
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = reader.pages[:limit]
    return "\n".join(page.extract_text() or "" for page in pages)


def extract_pdf_metadata(file_bytes: bytes) -> dict[str, str]:
    """Read /Title, /Author, /Subject, /Keywords from PDF metadata.
    These often reveal the true nature of the document (design system,
    template, manual, etc.) even when the body text looks resume-like."""
    out: dict[str, str] = {}
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        meta = reader.metadata or {}
        for raw_key, dest in (
            ("/Title", "title"),
            ("/Author", "author"),
            ("/Subject", "subject"),
            ("/Keywords", "keywords"),
            ("/Creator", "creator"),
            ("/Producer", "producer"),
        ):
            value = meta.get(raw_key)
            if value:
                out[dest] = str(value)
    except Exception as e:
        logger.warning("Failed to read PDF metadata: %s", e)
    return out


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


async def _append_dialog(api_post, screening_id: str, messages: list[dict], agency_id: str) -> None:
    async with httpx.AsyncClient(timeout=60.0) as client:
        await api_post(
            client,
            f"/internal/screenings/{screening_id}/dialog",
            {"messages": messages, "agency_id": agency_id},
        )


async def run_resume_pipeline(
    *,
    bot: Bot,
    chat_id: int,
    telegram_id: str,
    ctx: ContextTypes.DEFAULT_TYPE,
    agency_id: str,
    resume_input: ResumeInput,
    api_post,
    api_get=None,
    create_screening,
    cancel_reminder,
    create_reminder,
    final_message,
    persist_session=None,
) -> None:
    ud = ctx.user_data
    vacancy_id = ud.get("vacancy_id")
    vacancy_title = ud.get("vacancy_title", "")
    vacancy_company = ud.get("vacancy_company") or "Компания"
    ai_prompt = ud.get("ai_screening_prompt")
    vacancy_text = ud.get("vacancy_text") or vacancy_title

    try:
        if resume_input.kind == "pdf":
            if not resume_input.file_bytes:
                raise ValueError("Missing PDF bytes")
            from app.utils.file_validation import (
                ResumeFileTooLargeError,
                validate_resume_file_size,
            )

            try:
                validate_resume_file_size(len(resume_input.file_bytes))
            except ResumeFileTooLargeError:
                await bot.send_message(
                    chat_id,
                    "Файл слишком большой. Отправьте PDF до "
                    f"{MAX_RESUME_SIZE_MB} МБ.",
                )
                return

            resume_text = extract_pdf_text(resume_input.file_bytes)
            pdf_metadata = extract_pdf_metadata(resume_input.file_bytes)

            from app.utils.resume_validation import validate_resume_comprehensive

            # Stages 1-3: PDF metadata + hard reject patterns + structural
            # requirements (date periods, contacts, keywords). Fast & free.
            validation = validate_resume_comprehensive(
                resume_text, pdf_metadata=pdf_metadata
            )
            if not validation["is_valid"]:
                await bot.send_message(chat_id, _MSG_NOT_A_RESUME)
                logger.warning(
                    "Resume heuristics rejected: %s | meta=%s",
                    validation["reason"],
                    pdf_metadata,
                )
                return

        elif resume_input.kind == "hh_url":
            from app.services.hh_parser import parse_resume as hh_parse_resume

            hh_url = resume_input.resume_text or ""
            try:
                parsed = await asyncio.to_thread(hh_parse_resume, hh_url)
                resume_text = parsed.get("resume_text") or ""
            except Exception:
                logger.warning("hh.ru resume parse failed for %s", hh_url)
                resume_text = ""
            if not resume_text.strip():
                await bot.send_message(
                    chat_id,
                    "Не удалось загрузить резюме по ссылке.\n\n"
                    "Пожалуйста, скачайте PDF с hh.ru: «Моё резюме» → «Скачать» → PDF "
                    "и отправьте файл сюда.",
                )
                return
        else:
            resume_text = (resume_input.resume_text or "").strip()

        if not resume_text:
            await bot.send_message(
                chat_id,
                "Не удалось извлечь текст из резюме. "
                "Попробуйте другой PDF или отправьте текстом.",
            )
            return

        # Stage 4 (universal gate): LLM zero-shot classifier. Runs for PDF,
        # hh.ru import and free-form text — the heuristic stages above only
        # cover PDF, but a Figma export text pasted as message would slip
        # past them. The classifier is the catch-all.
        try:
            classification = await classify_document(resume_text)
        except Exception:
            logger.exception("Document classifier failed; allowing through")
            classification = {
                "is_resume": True,
                "confidence": 0.5,
                "doc_type": "unknown",
                "reason": "",
            }

        if (
            not classification.get("is_resume")
            or classification.get("confidence", 0.0) < 0.7
        ):
            await bot.send_message(chat_id, _MSG_NOT_A_RESUME)
            logger.warning(
                "Document classifier rejected: doc_type=%s confidence=%.2f reason=%s",
                classification.get("doc_type"),
                classification.get("confidence", 0.0),
                classification.get("reason"),
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
                    "agency_id": agency_id,
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
                        "agency_id": agency_id,
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
                            "agency_id": agency_id,
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

        turn = None
        if api_get is not None:
            try:
                turn = await start_structured_interview(
                    ud=ud,
                    api_get=api_get,
                    api_post=api_post,
                    first_name=first_name,
                    vacancy_id=str(vacancy_id),
                    agency_id=agency_id,
                    screening_id=str(screening_id),
                )
            except Exception:
                logger.exception("Structured interview start failed")

        if turn is None:
            # No question bank could be produced (no rubric, no LLM
            # suggestions, no fallback). Skip interview and finalize the
            # screening so the candidate at least gets resume-only scoring
            # and the recruiter sees them as "AI проверил".
            await finalize_screening(
                api_post, screening_id=str(screening_id), agency_id=agency_id
            )
            days = ud.get("feedback_days", 3)
            await bot.send_message(
                chat_id, final_message(first_name, days, had_questions=False)
            )
            ud["awaiting_questions"] = False
            ud["conversation_finished"] = True
            return

        bot_msg = turn.get("message", "")
        await bot.send_message(chat_id, bot_msg)
        await _append_dialog(
            api_post,
            screening_id,
            [{"role": "assistant", "content": bot_msg}],
            agency_id,
        )
        ud["dialog"] = [{"role": "assistant", "content": bot_msg}]
        ud["interview_turns"] = 1

        await create_reminder(
            telegram_id=telegram_id,
            state="waiting_answers",
            vacancy_title=vacancy_title,
            screening_id=screening_id,
        )
        ud["awaiting_questions"] = True
        ud["conversation_finished"] = False

    except Exception:
        logger.exception("Resume pipeline failed for chat_id=%s", chat_id)
        await bot.send_message(chat_id, _MSG_PIPELINE_ERROR)
    finally:
        ud["processing_resume"] = False
        if persist_session:
            if ud.get("conversation_finished"):
                step = "finished"
            elif ud.get("awaiting_questions"):
                step = "interview"
            else:
                step = "wait_resume"
            await persist_session(ctx, telegram_id, step=step)


async def run_interview_reply(
    *,
    bot: Bot,
    chat_id: int,
    ctx: ContextTypes.DEFAULT_TYPE,
    user_text: str,
    api_post,
    api_get=None,
    final_message,
) -> bool:
    """
    Handle one candidate reply in the structured interview.
    Returns True when the conversation has ended (screening is finalised).
    Generative free-form interviewing is intentionally not supported here —
    we always work off a fixed question bank produced at start time.
    """
    ud = ctx.user_data
    screening_id = ud.get("screening_id")
    if not screening_id:
        return True

    agency_id = str(ud.get("agency_id") or "")
    ud.setdefault("dialog", []).append({"role": "candidate", "content": user_text})
    await _append_dialog(
        api_post, screening_id, [{"role": "candidate", "content": user_text}], agency_id
    )

    if not use_structured_mode(ud):
        # Should not happen: pipeline always sets up a question bank or
        # finalises immediately. Defensive: end the conversation cleanly.
        await finalize_screening(
            api_post, screening_id=str(screening_id), agency_id=agency_id
        )
        name = ud.get("first_name", "Кандидат")
        days = ud.get("feedback_days", 3)
        await bot.send_message(chat_id, final_message(name, days, had_questions=False))
        ud["awaiting_questions"] = False
        ud["conversation_finished"] = True
        return True

    turn = await handle_structured_answer(
        user_text=user_text,
        ud=ud,
        api_post=api_post,
        agency_id=agency_id,
    )
    done = bool(turn.get("done"))
    bot_msg = turn.get("message", "")
    if bot_msg and not done:
        await bot.send_message(chat_id, bot_msg)
        ud["dialog"].append({"role": "assistant", "content": bot_msg})
        await _append_dialog(
            api_post,
            screening_id,
            [{"role": "assistant", "content": bot_msg}],
            agency_id,
        )

    if done:
        await finalize_screening(
            api_post, screening_id=str(screening_id), agency_id=agency_id
        )
        if not turn.get("early_exit"):
            name = ud.get("first_name", "Кандидат")
            days = ud.get("feedback_days", 3)
            await bot.send_message(
                chat_id, final_message(name, days, had_questions=True)
            )
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
