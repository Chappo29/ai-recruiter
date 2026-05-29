"""Telegram bot conversation handlers for candidate dialog."""

import logging
import re

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.core.config import DEFAULT_FEEDBACK_DAYS, MAX_RESUME_SIZE_MB, get_internal_api_key
from app.utils.file_validation import (
    ResumeFileTooLargeError,
    resume_size_limit_message,
    validate_resume_file_size,
)
from bot.vacancy_context import build_vacancy_text
from bot.session import clear_bot_session, save_bot_session
from bot.resume_pipeline import (
    ResumeInput,
    _MSG_DOCX_STUB,
    _MSG_PROCESSING_ACK,
    _MSG_PROCESSING_BUSY,
    run_interview_reply,
    run_resume_pipeline,
    schedule_resume_pipeline,
)

logger = logging.getLogger(__name__)

WAIT_VACANCY, WAIT_RESUME, ASKING_QUESTIONS, DONE = range(4)

_MSG_WRONG_DOC = (
    "❌ Нужен именно PDF файл.\n\n"
    "Как скачать с hh.ru:\n"
    "1. Зайдите на hh.ru → Моё резюме\n"
    "2. Нажмите «Скачать» → PDF\n"
    "Попробуйте ещё раз 👆"
)

_MSG_NEED_RESUME = (
    "📄 Отправьте резюме:\n"
    "• PDF-файл до {max_mb} МБ (скачать с hh.ru → «Скачать» → PDF)\n"
    "• или текстом — ссылка на hh.ru или кратко об опыте"
).format(max_mb=MAX_RESUME_SIZE_MB)

_MIN_TEXT_RESUME_LEN = 30
_HH_RESUME_URL_RE = re.compile(r'https?://([\w.]*\.)?hh\.(ru|kz|uz)/resume/\w+', re.I)


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
            "отправьте резюме PDF или текстом (ссылка hh.ru / описание опыта).",
            "",
            "PDF с hh.ru:",
            "1. Зайдите на hh.ru → Моё резюме",
            "2. «Скачать» → PDF",
            f"3. Отправьте файл сюда (до {MAX_RESUME_SIZE_MB} МБ) ⬆️",
        ]
    )
    return "\n".join(lines)


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


def build_conversation_handler(
    agency_id: str, backend_url: str
) -> tuple[ConversationHandler, object]:
    backend = backend_url.rstrip("/")

    async def _api_get(client: httpx.AsyncClient, path: str, **params):
        return await client.get(f"{backend}{path}", headers=_headers(), params=params)

    async def _api_post(client: httpx.AsyncClient, path: str, json: dict):
        return await client.post(f"{backend}{path}", headers=_headers(), json=json)

    async def _persist_session(
        ctx: ContextTypes.DEFAULT_TYPE,
        telegram_id: str,
        *,
        step: str | None = None,
    ) -> None:
        await save_bot_session(
            backend_url=backend,
            agency_id=agency_id,
            telegram_id=telegram_id,
            user_data=ctx.user_data,
            step=step,
        )

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        telegram_id = str(update.effective_user.id)
        await clear_bot_session(
            backend_url=backend,
            agency_id=agency_id,
            telegram_id=telegram_id,
        )
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
        ctx.user_data["feedback_days"] = data.get("feedback_days", DEFAULT_FEEDBACK_DAYS)

        if not vacancies:
            await update.message.reply_text(
                "Сейчас нет открытых вакансий. Загляните позже!"
            )
            return ConversationHandler.END

        ctx.user_data["_vacancies"] = vacancies

        keyboard = [
            [InlineKeyboardButton(v["title"], callback_data=str(v["id"]))]
            for v in vacancies
        ]
        await update.message.reply_text(
            "Привет! 👋 Выберите вакансию, на которую хотите откликнуться:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        await _persist_session(ctx, telegram_id, step="wait_vacancy")
        return WAIT_VACANCY

    async def handle_vacancy_choice(
        update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> int:
        query = update.callback_query
        await query.answer()

        vacancy_id = query.data
        title = "Вакансия"
        company = "Компания"
        ai_prompt = None
        requirements = None
        description = None

        cached = ctx.user_data.get("_vacancies")
        if cached:
            for v in cached:
                if str(v["id"]) == vacancy_id:
                    title = v.get("title") or title
                    company = v.get("company") or company
                    requirements = v.get("requirements")
                    description = v.get("description")
                    ai_prompt = v.get("ai_screening_prompt")
                    break
        else:
            async with httpx.AsyncClient(timeout=30.0) as client:
                vacancies_resp = await _api_get(
                    client, "/internal/vacancies/", agency_id=agency_id
                )
                if vacancies_resp.status_code == 200:
                    for v in vacancies_resp.json().get("vacancies") or []:
                        if str(v["id"]) == vacancy_id:
                            title = v.get("title") or title
                            company = v.get("company") or company
                            requirements = v.get("requirements")
                            description = v.get("description")
                            ai_prompt = v.get("ai_screening_prompt")
                            break

        ctx.user_data["vacancy_id"] = vacancy_id
        ctx.user_data["vacancy_title"] = title
        ctx.user_data["vacancy_company"] = company
        ctx.user_data["ai_screening_prompt"] = ai_prompt
        ctx.user_data["vacancy_text"] = build_vacancy_text(
            title=title,
            company=company,
            requirements=requirements,
            description=description,
        )

        await query.edit_message_text(_vacancy_chosen_message(title, company))

        await _create_reminder(
            telegram_id=str(query.from_user.id),
            state="waiting_resume",
            vacancy_title=title,
        )

        await _persist_session(ctx, str(query.from_user.id), step="wait_resume")
        return WAIT_RESUME

    async def _create_screening(
        vacancy_id: str, candidate_id: str, *, run_llm: bool = True
    ) -> str | None:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await _api_post(
                client,
                "/internal/screenings/",
                {
                    "vacancy_id": vacancy_id,
                    "candidate_id": candidate_id,
                    "agency_id": agency_id,
                    "run_llm": run_llm,
                },
            )
        if response.status_code in (200, 201):
            return response.json().get("id")
        logger.error(
            "Screening create failed: %s %s", response.status_code, response.text
        )
        return None

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
            logger.warning(
                "Failed to create reminder for telegram_id=%s",
                telegram_id,
                exc_info=True,
            )

    async def _cancel_reminder(telegram_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await _api_post(
                    client,
                    "/internal/reminders/cancel",
                    {"telegram_id": telegram_id, "agency_id": agency_id},
                )
        except Exception:
            logger.warning(
                "Failed to cancel reminder for telegram_id=%s",
                telegram_id,
                exc_info=True,
            )

    async def handle_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        message = update.message
        ud = ctx.user_data

        if ud.get("awaiting_questions"):
            return await handle_answer(update, ctx)

        if ud.get("conversation_finished"):
            await message.reply_text(
                "Ваш отклик уже принят. Нажмите /start, чтобы откликнуться снова."
            )
            return ConversationHandler.END

        if ud.get("processing_resume"):
            await message.reply_text(_MSG_PROCESSING_BUSY)
            return WAIT_RESUME

        resume_input: ResumeInput | None = None

        if message.document:
            file_name = (message.document.file_name or "").lower()
            if file_name.endswith(".docx") or file_name.endswith(".doc"):
                await message.reply_text(_MSG_DOCX_STUB)
                return WAIT_RESUME
            if not file_name.endswith(".pdf"):
                await message.reply_text(_MSG_WRONG_DOC)
                return WAIT_RESUME

            doc = message.document
            if doc.file_size is not None:
                try:
                    validate_resume_file_size(doc.file_size)
                except ResumeFileTooLargeError as exc:
                    await message.reply_text(
                        resume_size_limit_message(actual_bytes=exc.size_bytes)
                    )
                    return WAIT_RESUME

            try:
                tg_file = await doc.get_file()
                file_bytes = bytes(await tg_file.download_as_bytearray())
            except Exception:
                logger.exception("PDF download failed")
                await message.reply_text(
                    "Не удалось скачать файл. Попробуйте ещё раз."
                )
                return WAIT_RESUME

            try:
                validate_resume_file_size(len(file_bytes))
            except ResumeFileTooLargeError as exc:
                await message.reply_text(
                    resume_size_limit_message(actual_bytes=exc.size_bytes)
                )
                return WAIT_RESUME

            resume_input = ResumeInput(
                kind="pdf",
                file_bytes=file_bytes,
                filename=doc.file_name or "resume.pdf",
            )

        elif message.text:
            text = message.text.strip()
            if _HH_RESUME_URL_RE.search(text):
                resume_input = ResumeInput(kind="hh_url", resume_text=text)
            elif len(text) < _MIN_TEXT_RESUME_LEN:
                await message.reply_text(
                    "Пожалуйста, отправьте чуть подробнее: ссылку на резюме hh.ru "
                    "или краткое описание опыта (не менее нескольких предложений)."
                )
                return WAIT_RESUME
            else:
                resume_input = ResumeInput(kind="text", resume_text=text)

        else:
            await message.reply_text(_MSG_NEED_RESUME)
            return WAIT_RESUME

        ud["processing_resume"] = True
        ud["awaiting_questions"] = False
        ud["conversation_finished"] = False
        await _persist_session(ctx, str(update.effective_user.id), step="wait_resume")

        await message.reply_text(_MSG_PROCESSING_ACK)

        chat_id = update.effective_chat.id
        bot = ctx.application.bot

        async def _pipeline() -> None:
            await run_resume_pipeline(
                bot=bot,
                chat_id=chat_id,
                telegram_id=str(update.effective_user.id),
                ctx=ctx,
                agency_id=agency_id,
                resume_input=resume_input,
                api_post=_api_post,
                api_get=_api_get,
                create_screening=_create_screening,
                cancel_reminder=_cancel_reminder,
                create_reminder=_create_reminder,
                final_message=_final_message,
                persist_session=_persist_session,
            )

        schedule_resume_pipeline(bot=bot, chat_id=chat_id, ctx=ctx, coro_factory=_pipeline)
        return WAIT_RESUME

    async def handle_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        answer_text = (update.message.text or "").strip()
        if not answer_text:
            await update.message.reply_text("Пожалуйста, отправьте текстовый ответ.")
            return ASKING_QUESTIONS

        bot = ctx.application.bot
        chat_id = update.effective_chat.id

        finished = await run_interview_reply(
            bot=bot,
            chat_id=chat_id,
            ctx=ctx,
            user_text=answer_text,
            api_post=_api_post,
            api_get=_api_get,
            final_message=_final_message,
        )

        if finished:
            await _cancel_reminder(str(update.effective_user.id))
            await _persist_session(ctx, str(update.effective_user.id), step="finished")
            return ConversationHandler.END

        await _persist_session(ctx, str(update.effective_user.id), step="interview")
        return ASKING_QUESTIONS

    conv: ConversationHandler | None = None

    async def restore_session(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        from bot.session import conversation_state_for_step, load_bot_session

        if update.message and update.message.text:
            cmd = update.message.text.strip().split()[0].split("@")[0].lower()
            if cmd == "/start":
                return

        ud = ctx.user_data
        if ud.get("_session_loaded"):
            return

        ud["_session_loaded"] = True
        ud.setdefault("agency_id", agency_id)
        ud.setdefault("backend_url", backend)

        if not update.effective_user:
            return

        telegram_id = str(update.effective_user.id)
        stored = await load_bot_session(
            backend_url=backend,
            agency_id=agency_id,
            telegram_id=telegram_id,
        )
        if not stored:
            return

        ud.update(stored.get("user_data") or {})
        step = stored.get("step") or "wait_vacancy"

        if ud.get("processing_resume"):
            ud["processing_resume"] = False

        conv_state = conversation_state_for_step(step)
        if conv is not None and update.effective_chat:
            key = conv._get_key(update)
            if key is not None and conv_state is not None:
                conv._update_state(conv_state, key)

        if step == "interview" and update.message and not ud.get("_restore_notice"):
            ud["_restore_notice"] = True
            await update.message.reply_text("Продолжаем 👋")

    async def handle_unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Catch-all for messages outside an active conversation."""
        if update.message:
            await update.message.reply_text(
                "Привет! 👋 Чтобы откликнуться на вакансию, нажмите /start"
            )

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(~filters.COMMAND, handle_unknown),
        ],
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
    conv = conv_handler
    return conv_handler, restore_session
