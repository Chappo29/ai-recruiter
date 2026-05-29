"""
Многоэтапная валидация резюме.

Архитектура:
  Stage 1: PDF metadata (Title/Author/Subject/Keywords) — hard reject если
           документ объявлен как design system / blueprint / template / manual.
  Stage 2: Hard exclusion patterns в тексте — конкретные сигнатуры не-резюме.
  Stage 3: Структурные требования — period of employment (даты), контакты, ФИО.
  Stage 4: LLM-классификатор (вызывается отдельно из pipeline).

Heuristic-этапы быстрые и бесплатные; LLM — последняя линия.
"""

import re


# Ключевые слова резюме (positive signals).
RESUME_KEYWORDS = [
    r'\bопыт\s+работ[ыи]',
    r'\bобразование',
    r'\bнавык[иа]',
    r'\bдолжность',
    r'\bкомпани[яи]',
    r'\bпроект[ы]?',
    r'\bдостижени[яй]',
    r'\bрезюме',
    r'\bвакансия',
    r'\bработ[аы]',
    r'\bexperience',
    r'\beducation',
    r'\bskills',
    r'\bposition',
    r'\bcompany',
    r'\bprojects?',
    r'\bachievements?',
    r'\bresume',
    r'\bcv\b',
]

# Контактные паттерны.
CONTACT_PATTERNS = [
    r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
    r'\+?\d[\d\s\-()]{7,}\d',
    r'\btelegram\s*:\s*@\w+',
    r'\bwhatsapp\s*:\s*\+?\d',
    r'linkedin\.com/in/[\w\-]+',
    r'github\.com/[\w\-]+',
    r'hh\.(ru|kz|uz|by)/resume/',
]

# Мягкие «подозрительные» паттерны (как раньше).
SUSPICIOUS_PATTERNS = [
    r'\bсчет[- ]?фактура',
    r'\bдоговор',
    r'\bсоглашение',
    r'\bинструкция',
    r'\bотчет',
    r'\bпрезентация',
    r'\binvoice',
    r'\bcontract',
    r'\bagreement',
    r'\binstructions?',
    r'\breport',
    r'\bpresentation',
    r'\bмы\s+ищем',
    r'\bкого\s+мы\s+ищем',
    r'\bмы\s+предлагаем\:',
    r'\bчто\s+мы\s+предлагаем',
    r'\bчто\s+мы\s+ожидаем',
    r'\bтребования\s+к\s+кандидатам',
    r'\bусловия\s+работ[ыи]\:?\s*\n.*зарплата',
    r'\bоткликнуться\s+на\s+вакансию',
    r'\bотправить\s+резюме',
    r'\bjoin\s+our\s+team',
    r'\bwe\s+are\s+looking\s+for',
    r'\bwe\s+offer\:',
]

# HARD REJECT: явные сигнатуры документов, которые ТОЧНО не резюме.
# Эти паттерны не зависят от ФИО/контактов — если найдены, документ
# отвергается безусловно. Подобраны так, чтобы не появляться в нормальном
# резюме (даже у дизайнера).
HARD_REJECT_PATTERNS = [
    # Design / UI / product docs
    r'\bdesign\s+system\b',
    r'\bcomponent\s+library\b',
    r'\bstyle\s+guide\b',
    r'\bui\s+kit\b',
    r'\bui\s+system\b',
    r'\bfigma\s+(library|blueprint|template|kit)\b',
    r'\bblueprint\b',
    r'\bдизайн[- ]?система\b',
    r'\bбиблиотек[аи]\s+компонентов\b',
    r'\bстайлгайд\b',
    # Manuals / specifications / documentation
    r'\buser\s+manual\b',
    r'\bowner[\'’]?s\s+manual\b',
    r'\binstallation\s+guide\b',
    r'\bapi\s+reference\b',
    r'\btechnical\s+specification\b',
    r'\brelease\s+notes\b',
    r'\bchangelog\b',
    r'\bруководств[ао]\s+пользовател[яе]\b',
    r'\bтехническая\s+спецификация\b',
    r'\bтехническое\s+задание\b',
    # Templates / placeholders
    r'\blorem\s+ipsum\b',
    r'\bplaceholder\s+text\b',
    r'\btemplate\s+v\d',
    # Legal / financial
    r'\bterms\s+(of|and)\s+(service|conditions)\b',
    r'\bprivacy\s+policy\b',
    r'\bпубличн[аы][яй]\s+оферт[аы]\b',
    r'\bдоговор\s+(оказания|поставки|подряда|купли[- ]продажи)\b',
    # Education materials (not a person's education section)
    r'\blecture\s+notes\b',
    r'\bcourse\s+syllabus\b',
    r'\blesson\s+plan\b',
    # Marketing / sales decks
    r'\bpitch\s+deck\b',
    r'\bone[- ]?pager\b',
    r'\bsales\s+deck\b',
    # Articles / books
    r'\babstract[\s\n].*\bintroduction\b.*\bconclusion\b',
    r'\bchapter\s+\d+\b',
    r'\btable\s+of\s+contents\b',
]

# Паттерны периодов работы — «период с-по» в любом из распространённых форматов.
# Требуем хотя бы один такой период; без него документ не похож на трудовую биографию.
DATE_RANGE_PATTERNS = [
    # 2020 — 2024, 2020-2024, 2020–наст. время
    r'\b(19|20)\d{2}\s*[-–—]\s*((19|20)\d{2}|наст(оящее)?\.?\s*время|настоящ|present|now|current)\b',
    # 01.2020 — 03.2023, 01/2020 - 03/2023
    r'\b(0?[1-9]|1[0-2])[./](19|20)\d{2}\s*[-–—]\s*((0?[1-9]|1[0-2])[./](19|20)\d{2}|наст|present)\b',
    # Январь 2020 — Март 2023 / January 2020 - March 2023
    r'\b(январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр|january|february|march|april|may|june|july|august|september|october|november|december)[а-яa-z]*\s+(19|20)\d{2}\s*[-–—]\s*((январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр|january|february|march|april|may|june|july|august|september|october|november|december|наст|present|настоящ|now|current)[а-яa-z]*(\s+(19|20)\d{2})?)\b',
    # «с 09.2020», «с сентября 2020»
    r'\bс\s+(0?[1-9]|1[0-2])[./](19|20)\d{2}\b',
    r'\bс\s+(январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-я]*\s+(19|20)\d{2}\b',
]

# Паттерны в PDF metadata — если что-то из этого встречается в Title/Subject/Keywords,
# документ безусловно не резюме.
PDF_META_REJECT_TOKENS = [
    "blueprint",
    "design system",
    "ui kit",
    "ui system",
    "component library",
    "style guide",
    "стайлгайд",
    "design library",
    "figma",  # любой Figma-экспорт почти всегда не резюме
    "template",
    "manual",
    "руководство",
    "syllabus",
    "specification",
    "тз",
    "тех задание",
    "техническое задание",
    "pitch deck",
    "white paper",
    "whitepaper",
    "datasheet",
    "release notes",
    "changelog",
]


def check_pdf_metadata_reject(pdf_metadata: dict[str, str] | None) -> str | None:
    """Stage 1. Returns rejection reason or None."""
    if not pdf_metadata:
        return None
    blob = " ".join(str(v) for v in pdf_metadata.values() if v).lower()
    for token in PDF_META_REJECT_TOKENS:
        if token in blob:
            return f'PDF metadata содержит "{token}"'
    return None


def check_hard_reject_patterns(text: str) -> str | None:
    """Stage 2. Returns rejection reason or None."""
    if not text:
        return None
    text_lower = text.lower()
    for pattern in HARD_REJECT_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL)
        if match:
            return f'найден паттерн не-резюме: "{match.group(0)[:60]}"'
    return None


def check_has_date_periods(text: str) -> bool:
    """Stage 3a. True if at least one employment-style date range is present."""
    if not text:
        return False
    for pattern in DATE_RANGE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def check_resume_contains_name(text: str) -> bool:
    """Проверяет наличие ФИО (двух слов с заглавной буквы) в первых 500 символах."""
    if not text:
        return False
    snippet = text[:500]
    name_pattern = r'\b([А-ЯЁA-Z][а-яёa-z]+)\s+([А-ЯЁA-Z][а-яёa-z]+)\b'
    matches = re.findall(name_pattern, snippet)
    return len(matches) >= 1


def check_resume_contains_contact(text: str) -> bool:
    if not text:
        return False
    snippet = text[:2000].lower()
    for pattern in CONTACT_PATTERNS:
        if re.search(pattern, snippet, re.IGNORECASE):
            return True
    return False


def validate_resume_text(text: str, min_length: int = 50) -> dict:
    """Базовая лёгкая валидация (без LLM, без metadata)."""
    if not text or len(text.strip()) < min_length:
        return {
            "is_valid": False,
            "confidence": 0.0,
            "reason": "Слишком короткий текст или пустой документ",
        }

    text_lower = text.lower()
    has_name = check_resume_contains_name(text)
    has_contact = check_resume_contains_contact(text)

    # Hard reject — переоценивает любые позитивные сигналы.
    hard = check_hard_reject_patterns(text)
    if hard:
        return {
            "is_valid": False,
            "confidence": 0.0,
            "reason": f"Документ не похож на резюме: {hard}",
        }

    # Suspicious patterns — мягкая проверка (как раньше).
    suspicious_found = [
        p for p in SUSPICIOUS_PATTERNS if re.search(p, text_lower, re.IGNORECASE)
    ]
    if suspicious_found and not (has_name or has_contact):
        return {
            "is_valid": False,
            "confidence": 0.1,
            "reason": f"Подозрительные паттерны: {', '.join(suspicious_found[:3])}",
        }

    # Подсчёт ключевых слов.
    keywords_found = sum(
        1 for p in RESUME_KEYWORDS if re.search(p, text_lower, re.IGNORECASE)
    )
    if has_contact:
        min_keywords = 1
    elif has_name:
        min_keywords = 2
    else:
        min_keywords = 4

    confidence = min(keywords_found / len(RESUME_KEYWORDS), 1.0)
    if keywords_found >= min_keywords:
        return {
            "is_valid": True,
            "confidence": confidence,
            "reason": f"Найдено {keywords_found} ключевых слов резюме",
        }
    return {
        "is_valid": False,
        "confidence": confidence,
        "reason": (
            f"Найдено только {keywords_found} ключевых слов (минимум {min_keywords})"
        ),
    }


def validate_resume_comprehensive(
    text: str, *, pdf_metadata: dict[str, str] | None = None
) -> dict:
    """
    Многоэтапная проверка (без LLM). Возвращает {is_valid, confidence, checks, reason}.
    LLM-классификатор вызывается отдельно из пайплайна (resume_pipeline.py).
    """
    checks = {
        "length": len(text.strip()) >= 50,
        "pdf_metadata_ok": True,
        "no_hard_reject": True,
        "has_date_periods": False,
        "has_name_or_contact": False,
        "keywords": False,
    }

    meta_reject = check_pdf_metadata_reject(pdf_metadata)
    if meta_reject:
        checks["pdf_metadata_ok"] = False

    hard = check_hard_reject_patterns(text)
    if hard:
        checks["no_hard_reject"] = False

    checks["has_date_periods"] = check_has_date_periods(text)
    has_name = check_resume_contains_name(text)
    has_contact = check_resume_contains_contact(text)
    checks["has_name_or_contact"] = has_name or has_contact

    basic = validate_resume_text(text)
    checks["keywords"] = basic["is_valid"]

    # PDF metadata-based reject is absolute: если документ ОБЪЯВЛЕН как
    # design system / template / manual в собственных метаданных — это не
    # резюме, даже если автор упомянул своё имя.
    if not checks["pdf_metadata_ok"]:
        return {
            "is_valid": False,
            "confidence": 0.0,
            "checks": checks,
            "reason": f"Жёсткий отказ: {meta_reject}",
        }

    # Hard-reject paтterns в тексте — НЕ абсолютны: настоящий дизайнер
    # может упомянуть «built a design system at Acme». Отвергаем только
    # если ОДНОВРЕМЕННО нет сильных позитивных сигналов (даты + контакты).
    strong_positive = checks["has_date_periods"] and has_contact
    if not checks["no_hard_reject"] and not strong_positive:
        return {
            "is_valid": False,
            "confidence": 0.0,
            "checks": checks,
            "reason": (
                f"Жёсткий отказ: {hard} (нет дат периодов работы и контактов, "
                "которые указали бы на личное резюме)"
            ),
        }

    # Soft accept: требуем дата-периоды + контакты/имя + ключевые слова.
    required = ("length", "has_date_periods", "has_name_or_contact", "keywords")
    passed = sum(1 for k in required if checks[k])
    confidence = passed / len(required)
    is_valid = passed == len(required)  # все четыре

    if is_valid:
        reason = f"Пройдено {passed}/{len(required)} обязательных проверок"
    else:
        failed = [k for k in required if not checks[k]]
        reason = f"Не пройдены проверки: {', '.join(failed)}"

    return {
        "is_valid": is_valid,
        "confidence": confidence,
        "checks": checks,
        "reason": reason,
    }
