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
    full_name = full_name.strip()
    first_name = first_name.strip()
    if first_name and " " not in first_name:
        return first_name
    if full_name:
        return full_name.split()[0]
    return "Кандидат"


async def extract_candidate_name_from_resume(resume_text: str) -> dict[str, str]:
    snippet = resume_text[:8000]
    prompt = (
        "Извлеки из резюме полное имя кандидата (имя и фамилию).\n"
        "Верни ТОЛЬКО JSON:\n"
        '{"full_name": "Имя Фамилия", "first_name": "Имя"}\n\n'
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

    if not full_name:
        full_name = "Кандидат"

    first_name = _first_name_only(full_name, first_name)

    return {
        "first_name": first_name,
        "last_name": "",
        "full_name": full_name,
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
