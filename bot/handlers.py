"""Telegram bot conversation handlers for candidate dialog."""

import base64
import io
import logging

import httpx
from pypdf import PdfReader
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.core.config import get_internal_api_key
from app.services.llm_service import extract_candidate_name_from_resume

logger = logging.getLogger(__name__)

WAIT_VACANCY, WAIT_RESUME, ASKING_QUESTIONS, DONE = range(4)

_MSG_WRONG_DOC = (
    "❌ Нужен именно PDF файл.\n\n"
    "Как скачать с hh.ru:\n"
    "1. Зайдите на hh.ru → Моё резюме\n"
    "2. Нажмите «Скачать» → PDF\n"
    "Попробуйте ещё раз 👆"
)

_MSG_TEXT_INSTEAD_PDF = (
    "📄 Пожалуйста, отправьте файл PDF, а не текст.\n\n"
    "Как скачать с hh.ru:\n"
    "1. Зайдите на hh.ru → Моё резюме\n"
    "2. Нажмите «Скачать» → PDF\n"
    "Попробуйте ещё раз 👆"
)

_MSG_NEED_PDF = "📄 Нужен PDF файл резюме.\nПопробуйте ещё раз 👆"


def _headers() -> dict[str, str]:
    return {"X-Internal-Key": get_internal_api_key()}


def _vacancy_chosen_message(title: str, company: str | None) -> str:
    lines = [
        "Отличный выбор! 👋",
        "",
        f"Вы выбрали: {title}",
    ]
    if company and company.strip():
        lines.append(f"Компания: {company.strip()}")
    lines.extend(
        [
            "",
            f"Для участия в отборе на позицию {title}",
            "отправьте резюме в формате PDF.",
            "",
            "Как скачать с hh.ru:",
            "1. Зайдите на hh.ru → Моё резюме",
            "2. Нажмите «Скачать» → PDF",
            "3. Отправьте файл сюда ⬆️",
        ]
    )
    return "\n".join(lines)


def _first_question_message(name: str, total: int, question_text: str) -> str:
    return (
        f"Спасибо, {name}! 😊\n\n"
        "Прежде чем передать вашу кандидатуру рекрутеру, "
        "задам несколько коротких вопросов.\n\n"
        f"Вопрос 1 из {total}:\n{question_text}"
    )


def _next_question_message(n: int, total: int, question_text: str) -> str:
    return f"Вопрос {n} из {total}:\n{question_text}"


def _final_message(name: str, days: int, *, had_questions: bool) -> str:
    if had_questions:
        intro = f"Спасибо за ваши ответы, {name}! 🙏"
    else:
        intro = f"Спасибо, {name}! 🙏"
    return (
        f"{intro}\n\n"
        "Ваша кандидатура передана рекрутеру.\n"
        f"Мы рассмотрим её и в течение {days} рабочих "
        "дней пришлём обратную связь.\n\n"
        "Удачи! 🍀"
    )


def build_conversation_handler(agency_id: str, backend_url: str) -> ConversationHandler:
    backend = backend_url.rstrip("/")

    async def _api_get(client: httpx.AsyncClient, path: str, **params):
        return await client.get(f"{backend}{path}", headers=_headers(), params=params)

    async def _api_post(client: httpx.AsyncClient, path: str, json: dict):
        return await client.post(f"{backend}{path}", headers=_headers(), json=json)

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        ctx.user_data.clear()
        ctx.user_data["agency_id"] = agency_id
        ctx.user_data["backend_url"] = backend

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await _api_get(
                client, "/internal/vacancies/", agency_id=agency_id
            )

        if response.status_code != 200:
            await update.message.reply_text(
                "Не удалось загрузить вакансии. Попробуйте позже."
            )
            return ConversationHandler.END

        data = response.json()
        vacancies = data.get("vacancies") or []
        ctx.user_data["feedback_days"] = data.get("feedback_days", 3)

        if not vacancies:
            await update.message.reply_text(
                "Сейчас нет открытых вакансий. Загляните позже!"
            )
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton(v["title"], callback_data=str(v["id"]))]
            for v in vacancies
        ]
        await update.message.reply_text(
            "Привет! 👋 Выберите вакансию, на которую хотите откликнуться:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return WAIT_VACANCY

    async def handle_vacancy_choice(
        update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> int:
        query = update.callback_query
        await query.answer()

        vacancy_id = query.data
        title = "Вакансия"
        company = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            vacancies_resp = await _api_get(
                client, "/internal/vacancies/", agency_id=agency_id
            )
            if vacancies_resp.status_code == 200:
                for v in vacancies_resp.json().get("vacancies") or []:
                    if str(v["id"]) == vacancy_id:
                        title = v.get("title") or title
                        company = v.get("company")
                        break

        ctx.user_data["vacancy_id"] = vacancy_id
        ctx.user_data["vacancy_title"] = title
        ctx.user_data["vacancy_company"] = company

        await query.edit_message_text(_vacancy_chosen_message(title, company))

        # State A: candidate chose vacancy but hasn't sent resume yet
        await _create_reminder(
            telegram_id=str(query.from_user.id),
            state="waiting_resume",
            vacancy_title=title,
        )

        return WAIT_RESUME

    def _extract_pdf_text_from_bytes(file_bytes: bytes) -> str:
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    async def _create_screening(
        vacancy_id: str, candidate_id: str, *, run_llm: bool = True
    ) -> str | None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await _api_post(
                client,
                "/internal/screenings/",
                {
                    "vacancy_id": vacancy_id,
                    "candidate_id": candidate_id,
                    "run_llm": run_llm,
                },
            )
        if response.status_code in (200, 201):
            return response.json().get("id")
        logger.error(
            "Screening create failed: %s %s", response.status_code, response.text
        )
        return None

    async def _complete_screening(screening_id: str) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{backend}/internal/screenings/{screening_id}/complete",
                headers=_headers(),
            )
        if response.status_code not in (200, 201):
            logger.error(
                "Screening complete failed: %s %s", response.status_code, response.text
            )

    async def _create_reminder(
        telegram_id: str,
        state: str,
        vacancy_title: str,
        screening_id: str | None = None,
    ) -> None:
        payload: dict = {
            "telegram_id": telegram_id,
            "agency_id": agency_id,
            "state": state,
            "vacancy_title": vacancy_title,
        }
        if screening_id:
            payload["screening_id"] = screening_id
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await _api_post(client, "/internal/reminders/", payload)
        except Exception:
            logger.warning("Failed to create reminder for telegram_id=%s", telegram_id, exc_info=True)

    async def _cancel_reminder(telegram_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await _api_post(
                    client,
                    "/internal/reminders/cancel",
                    {"telegram_id": telegram_id},
                )
        except Exception:
            logger.warning("Failed to cancel reminder for telegram_id=%s", telegram_id, exc_info=True)

    async def _load_questions(vacancy_id: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{backend}/internal/questions/vacancy/{vacancy_id}",
                headers=_headers(),
            )
        if response.status_code != 200:
            return []
        return response.json() or []

    async def _send_final_message(
        update: Update, ctx: ContextTypes.DEFAULT_TYPE, *, had_questions: bool
    ) -> int:
        name = ctx.user_data.get("first_name", "Кандидат")
        days = ctx.user_data.get("feedback_days", 3)
        await update.message.reply_text(
            _final_message(name, days, had_questions=had_questions)
        )
        return ConversationHandler.END

    async def _ask_current_question(
        update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> int:
        questions = ctx.user_data.get("questions") or []
        index = ctx.user_data.get("question_index", 0)
        total = len(questions)

        if index >= total:
            return await _send_final_message(update, ctx, had_questions=total > 0)

        question = questions[index]
        name = ctx.user_data.get("first_name", "Кандидат")

        if index == 0:
            text = _first_question_message(name, total, question["text"])
        else:
            text = _next_question_message(index + 1, total, question["text"])

        await update.message.reply_text(text)
        return ASKING_QUESTIONS

    async def handle_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        message = update.message

        if message.document:
            file_name = (message.document.file_name or "").lower()
            if not file_name.endswith(".pdf"):
                await message.reply_text(_MSG_WRONG_DOC)
                return WAIT_RESUME

            doc = message.document
            try:
                tg_file = await doc.get_file()
                file_bytes = bytes(await tg_file.download_as_bytearray())
                resume_text = _extract_pdf_text_from_bytes(file_bytes)
            except Exception:
                logger.exception("PDF extraction failed")
                await message.reply_text(
                    "Не удалось прочитать PDF. Попробуйте другой файл."
                )
                return WAIT_RESUME

            if not resume_text or not resume_text.strip():
                await message.reply_text(
                    "Не удалось извлечь текст из PDF. Попробуйте другой файл."
                )
                return WAIT_RESUME

        elif message.text:
            await message.reply_text(_MSG_TEXT_INSTEAD_PDF)
            return WAIT_RESUME

        else:
            await message.reply_text(_MSG_NEED_PDF)
            return WAIT_RESUME

        try:
            name_data = await extract_candidate_name_from_resume(resume_text)
        except Exception:
            logger.exception("Failed to extract name via LLM")
            name_data = {
                "first_name": "Кандидат",
                "last_name": "",
                "full_name": "Кандидат",
            }

        ctx.user_data["first_name"] = name_data["first_name"]
        ctx.user_data["full_name"] = name_data["full_name"]
        ctx.user_data["resume_text"] = resume_text

        telegram_id = str(update.effective_user.id)
        vacancy_id = ctx.user_data["vacancy_id"]

        async with httpx.AsyncClient(timeout=120.0) as client:
            cand_response = await _api_post(
                client,
                "/internal/candidates/",
                {
                    "full_name": name_data["full_name"],
                    "telegram_id": telegram_id,
                    "resume_text": resume_text,
                },
            )

        if cand_response.status_code not in (200, 201):
            await message.reply_text(
                "Не удалось сохранить данные. Попробуйте позже."
            )
            return WAIT_RESUME

        candidate_id = cand_response.json()["id"]
        ctx.user_data["candidate_id"] = candidate_id

        file_b64 = base64.b64encode(file_bytes).decode()
        async with httpx.AsyncClient(timeout=60.0) as client:
            upload_resp = await _api_post(
                client,
                "/internal/candidates/upload-resume",
                {
                    "candidate_id": candidate_id,
                    "file_base64": file_b64,
                    "filename": doc.file_name or "resume.pdf",
                },
            )
        if upload_resp.status_code not in (200, 201):
            logger.warning(
                "Resume PDF upload failed: %s %s",
                upload_resp.status_code,
                upload_resp.text,
            )

        questions = await _load_questions(vacancy_id)
        ctx.user_data["questions"] = questions
        ctx.user_data["answers"] = []
        ctx.user_data["question_index"] = 0

        # Cancel State A reminder — resume has been received
        await _cancel_reminder(telegram_id)

        if not questions:
            screening_id = await _create_screening(
                vacancy_id, candidate_id, run_llm=True
            )
            if screening_id:
                ctx.user_data["screening_id"] = screening_id
            else:
                logger.warning("Screening id missing after resume")
            return await _send_final_message(update, ctx, had_questions=False)

        screening_id = await _create_screening(
            vacancy_id, candidate_id, run_llm=False
        )
        if screening_id:
            ctx.user_data["screening_id"] = screening_id
            # State B: resume received, now waiting for question answers
            await _create_reminder(
                telegram_id=telegram_id,
                state="waiting_answers",
                vacancy_title=ctx.user_data.get("vacancy_title", ""),
                screening_id=screening_id,
            )
        else:
            logger.warning("Screening id missing; answers may not be saved")

        return await _ask_current_question(update, ctx)

    async def handle_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        answer_text = (update.message.text or "").strip()
        if not answer_text:
            await update.message.reply_text("Пожалуйста, отправьте текстовый ответ.")
            return ASKING_QUESTIONS

        questions = ctx.user_data.get("questions") or []
        index = ctx.user_data.get("question_index", 0)

        if index >= len(questions):
            return await _send_final_message(update, ctx, had_questions=True)

        question = questions[index]
        screening_id = ctx.user_data.get("screening_id")

        if screening_id:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await _api_post(
                    client,
                    "/internal/answers/",
                    {
                        "screening_id": screening_id,
                        "question_id": question["id"],
                        "answer_text": answer_text,
                    },
                )

        ctx.user_data.setdefault("answers", []).append(answer_text)
        ctx.user_data["question_index"] = index + 1

        if ctx.user_data["question_index"] < len(questions):
            next_index = ctx.user_data["question_index"]
            total = len(questions)
            next_q = questions[next_index]
            await update.message.reply_text(
                _next_question_message(next_index + 1, total, next_q["text"])
            )
            return ASKING_QUESTIONS

        if screening_id:
            await _complete_screening(screening_id)

        # All questions answered — cancel State B reminder
        await _cancel_reminder(str(update.effective_user.id))

        return await _send_final_message(update, ctx, had_questions=True)

    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAIT_VACANCY: [
                CallbackQueryHandler(handle_vacancy_choice, pattern=r"^.+$"),
            ],
            WAIT_RESUME: [
                MessageHandler(~filters.COMMAND, handle_resume),
            ],
            ASKING_QUESTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
