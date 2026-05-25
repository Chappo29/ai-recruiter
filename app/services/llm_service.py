import httpx
import json
import logging

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b-instruct"

SCREENING_SYSTEM_PROMPT = """
Ты — старший рекрутер с 10-летним опытом.
Твоя задача: оценить кандидата на соответствие вакансии.

Ты получишь:
1. ВАКАНСИЯ: требования и описание позиции
2. РЕЗЮМЕ: текст резюме кандидата

## ЧАСТЬ 1 — Скрининг на соответствие
Оцени кандидата по критериям:
- Соответствие hard skills требованиям вакансии
- Релевантный опыт (индустрия, роль, масштаб)
- Конкретика в достижениях (цифры, результаты, метрики)
- Красные флаги (частая смена работ, gaps, размытые формулировки)

## ЧАСТЬ 2 — Детектор вкатуна и ИИ-резюме
Признаки ИИ-сгенерированного резюме:
- Идеальная структура без живых деталей
- Обтекаемые глаголы: участвовал, вносил вклад, помогал, был частью команды
- Нет провалов и незаконченных проектов
- Все цифры округлены до красивых значений (ровно 40%, ровно в 2 раза)
- Одинаковый канцелярский стиль по всем разделам
- Навыки перечислены без контекста применения

Признаки вкатуна:
- Опыт только на курсах и pet-проектах без реального результата
- Достижения размытые: улучшил, оптимизировал — без цифр
- Портфолио из типовых учебных проектов (todo-app, интернет-магазин)
- Не указаны конкретные инструменты и технологии с контекстом

Верни ответ СТРОГО в формате JSON без markdown, без пояснений, без текста до и после:
{
  "verdict": "fit или maybe или reject",
  "score": число от 0 до 100,
  "summary": "3-4 предложения кто этот кандидат и почему подходит или нет",
  "strengths": ["сильная сторона 1", "сильная сторона 2"],
  "weaknesses": ["слабая сторона 1", "слабая сторона 2"],
  "ai_markers": {
    "suspected": true или false,
    "confidence": "low или medium или high",
    "reasons": ["причина 1", "причина 2"]
  },
  "red_flags": ["флаг 1", "флаг 2"],
  "verification_questions": [
    "Конкретный вопрос по реальному достижению из резюме 1",
    "Конкретный вопрос по реальному достижению из резюме 2",
    "Конкретный вопрос по реальному достижению из резюме 3"
  ]
}
"""

async def run_screening(vacancy_text: str, resume_text: str) -> dict:
    user_message = f"ВАКАНСИЯ:\n{vacancy_text}\n\nРЕЗЮМЕ КАНДИДАТА:\n{resume_text}"

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": SCREENING_SYSTEM_PROMPT + "\n\n" + user_message,
        "stream": False,
        "format": "json"
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        raw = response.json()["response"].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        clean = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)


QUESTIONS_SUGGEST_PROMPT = """
На основе вакансии предложи 5 конкретных вопросов для проверки кандидата на собеседовании.
Вопросы должны проверять реальный опыт, не теорию.

Верни ответ СТРОГО в формате JSON без markdown, без пояснений:
{"questions": ["вопрос1", "вопрос2", "вопрос3", "вопрос4", "вопрос5"]}
"""


async def suggest_interview_questions(vacancy_text: str) -> dict:
    user_message = f"ВАКАНСИЯ:\n{vacancy_text}"

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": QUESTIONS_SUGGEST_PROMPT + "\n\n" + user_message,
        "stream": False,
        "format": "json",
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        raw = response.json()["response"].strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)

    questions = result.get("questions") or []
    if not isinstance(questions, list):
        questions = []
    return {"questions": [str(q) for q in questions if q]}


def _compose_full_name(first_name: str, last_name: str) -> str:
    parts = [p.strip() for p in (first_name, last_name) if p and str(p).strip()]
    return " ".join(parts) if parts else "Кандидат"


def _first_name_only(full_name: str, first_name: str) -> str:
    """Keep only the given name for bot greetings, not surname."""
    from app.utils.name import extract_first_name

    fn = (first_name or "").strip()
    if fn and " " not in fn:
        return fn
    return extract_first_name(full_name)


async def extract_candidate_name_from_resume(resume_text: str) -> dict[str, str]:
    snippet = resume_text[:8000]
    prompt = (
        "Извлеки из резюме ФИО кандидата (обычно в первой строке, часто «Фамилия Имя»).\n"
        "full_name — как в резюме (обе части). first_name — только имя для обращения.\n"
        "Пример: «Биценко Владислав» → full_name «Биценко Владислав», first_name «Владислав».\n"
        "Верни ТОЛЬКО JSON:\n"
        '{"full_name": "Фамилия Имя", "first_name": "Имя"}\n\n'
        f"Резюме: {snippet}"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        raw = response.json()["response"].strip()

    result = _parse_llm_json(raw)
    full_name = str(result.get("full_name") or "").strip()
    first_name = str(result.get("first_name") or "").strip()

    if not full_name:
        last_name = str(result.get("last_name") or "").strip()
        legacy_first = str(result.get("first_name") or "").strip()
        if legacy_first or last_name:
            full_name = _compose_full_name(legacy_first, last_name)

    from app.utils.name import parse_candidate_names

    names = parse_candidate_names(
        resume_text,
        llm_full_name=full_name if full_name != "Кандидат" else None,
        llm_first_name=first_name or None,
    )
    return {
        "first_name": names["first_name"],
        "last_name": "",
        "full_name": names["full_name"],
    }


async def extract_full_name_from_resume(resume_text: str) -> str:
    data = await extract_candidate_name_from_resume(resume_text)
    return data["full_name"]


async def extract_name_from_resume(resume_text: str) -> str:
    """Alias: returns full name."""
    return await extract_full_name_from_resume(resume_text)


EVALUATE_ANSWERS_PROMPT = """
Ты опытный рекрутер. Оцени ответы кандидата на вопросы интервью.

Важно: правильных ответов нет — оценивай глубину опыта,
конкретику, честность. Учитывай что люди пишут неформально,
могут ошибаться в словах, использовать сленг.

{qa_pairs}

Верни ответ СТРОГО в формате JSON без markdown, без пояснений:
{{
  "answers_summary": "общий вывод по ответам 2-3 предложения",
  "answers_score": 0-100,
  "strong_answers": ["вопрос где ответил хорошо"],
  "weak_answers": ["вопрос где ответил слабо или уклончиво"]
}}
"""


def _parse_llm_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        clean = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)


BOT_INTERVIEW_SYSTEM = """
Ты — дружелюбный HR-ассистент в Telegram. Веди короткий диалог с кандидатом после получения резюме.

Правила:
- Задавай ровно 1 вопрос за сообщение.
- ОБЯЗАТЕЛЬНО опирайся на блок «Вводные рекрутера» — задай вопросы по каждому важному пункту оттуда.
- Пока не задано достаточно вопросов (см. счётчики ниже), НЕ завершай диалог: "done" должно быть false.
- На первом сообщении кандидату всегда "done": false и вопрос по вводным рекрутера / резюме.
- Завершай ("done": true) только когда задано не меньше минимума вопросов и кандидат ответил на последний.

Верни СТРОГО JSON:
{
  "message": "текст сообщения кандидату (с вопросом)",
  "done": false
}
"""


def _count_assistant_messages(dialog: list[dict]) -> int:
    return sum(1 for e in dialog if (e.get("role") or "").lower() == "assistant")


def _min_interview_questions(ai_screening_prompt: str | None) -> int:
    if ai_screening_prompt and ai_screening_prompt.strip():
        return 3
    return 2


def fallback_interview_question(
    ai_screening_prompt: str | None, *, first_name: str = "коллега"
) -> str:
    focus = (ai_screening_prompt or "").strip()
    if focus:
        return (
            f"Спасибо, {first_name}! 😊\n\n"
            f"Чтобы лучше понять вашу кандидатуру, расскажите, пожалуйста: {focus}"
        )
    return (
        f"Спасибо, {first_name}! 😊\n\n"
        "Расскажите, пожалуйста, почему вас заинтересовала эта позиция "
        "и какой релевантный опыт вы хотите применить?"
    )


async def run_bot_interview_turn(
    *,
    vacancy_title: str,
    company: str,
    vacancy_text: str,
    ai_screening_prompt: str | None,
    resume_text: str,
    dialog: list[dict],
    candidate_message: str | None = None,
    candidate_first_name: str = "коллега",
) -> dict:
    focus = (ai_screening_prompt or "").strip() or (
        "Уточни мотивацию, релевантный опыт и ожидания по зарплате."
    )
    min_questions = _min_interview_questions(ai_screening_prompt)
    assistant_sent = _count_assistant_messages(dialog)
    is_opening = candidate_message is None and assistant_sent == 0

    history_lines = []
    for entry in dialog[-12:]:
        role = entry.get("role", "user")
        text = entry.get("content") or entry.get("text") or ""
        if isinstance(text, dict):
            text = str(text)
        history_lines.append(f"{role}: {text}")
    if candidate_message:
        history_lines.append(f"candidate: {candidate_message}")

    user_block = (
        f"Вакансия: {vacancy_title} ({company})\n"
        f"Описание вакансии:\n{vacancy_text}\n\n"
        f"Вводные рекрутера (приоритет для вопросов):\n{focus}\n\n"
        f"Резюме кандидата:\n{resume_text[:6000]}\n\n"
        f"Уже задано вопросов ботом: {assistant_sent}\n"
        f"Минимум вопросов перед завершением: {min_questions}\n"
        f"Это первое сообщение кандидату: {'да' if is_opening else 'нет'}\n\n"
        f"История диалога:\n" + ("\n".join(history_lines) if history_lines else "(начало)")
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": BOT_INTERVIEW_SYSTEM + "\n\n" + user_block,
        "stream": False,
        "format": "json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        raw = response.json()["response"].strip()

    result = _parse_llm_json(raw)
    message = str(result.get("message") or "").strip()
    done = bool(result.get("done"))

    if not message:
        message = fallback_interview_question(ai_screening_prompt, first_name=candidate_first_name)
        done = False

    # Не завершать раньше минимума вопросов (считаем сообщение, которое сейчас отправим)
    if done and (assistant_sent + 1) < min_questions:
        done = False
        if "?" not in message:
            message = fallback_interview_question(
                ai_screening_prompt, first_name=candidate_first_name
            )

    if is_opening:
        done = False

    return {"message": message, "done": done}


async def evaluate_interview_answers(qa_pairs_text: str) -> dict:
    prompt = EVALUATE_ANSWERS_PROMPT.format(qa_pairs=qa_pairs_text)

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        raw = response.json()["response"].strip()

    result = _parse_llm_json(raw)

    score = result.get("answers_score")
    if score is not None:
        result["answers_score"] = int(score)

    for key in ("strong_answers", "weak_answers"):
        if not isinstance(result.get(key), list):
            result[key] = []

    return result
