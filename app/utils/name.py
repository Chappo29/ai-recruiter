"""Extract and normalize candidate names (Russian-style heuristics)."""

import re

SURNAME_SUFFIXES = (
    "ов",
    "ев",
    "ёв",
    "ин",
    "ын",
    "ий",
    "ая",
    "яя",
    "ко",
    "юк",
    "енко",
    "ская",
    "ский",
)


def looks_like_surname(word: str) -> bool:
    lower = word.lower().strip()
    if len(lower) < 3:
        return False
    return any(lower.endswith(suffix) for suffix in SURNAME_SUFFIXES)


def extract_first_name(full_name: str | None) -> str:
    """
    «Иванов Иван» → «Иван», «Иван Иванов» → «Иван».
    """
    if not full_name or not str(full_name).strip():
        return "Кандидат"

    parts = [p for p in str(full_name).strip().split() if p]
    if len(parts) == 1:
        return parts[0]
    if len(parts) >= 2:
        first, second = parts[0], parts[1]
        if looks_like_surname(first) and not looks_like_surname(second):
            return second
        if looks_like_surname(second) and not looks_like_surname(first):
            return first
        return first
    return "Кандидат"


_SKIP_LINE_RE = re.compile(
    r"@|https?://|www\.|\+?\d[\d\s\-\(\)]{8,}|руб|₽|mail\.|telegram|\.ru\b",
    re.IGNORECASE,
)
_NAME_LINE_RE = re.compile(
    r"^[А-ЯЁA-Z][а-яёa-z]{1,}(?:-[А-ЯЁA-Z][а-яёa-z]+)?"
    r"\s+[А-ЯЁA-Z][а-яёa-z]{1,}(?:-[А-ЯЁA-Z][а-яёa-z]+)?"
    r"(?:\s+[А-ЯЁA-Z]\.)?$"
)
_SKIP_WORDS = frozenset(
    {"мужчина", "женщина", "резюме", "опыт", "работы", "контакты", "образование"}
)


def parse_name_from_resume_text(resume_text: str | None) -> str | None:
    """Первая строка резюме вида «Биценко Владислав» (hh.ru и аналоги)."""
    if not resume_text or not str(resume_text).strip():
        return None

    for line in resume_text.splitlines()[:15]:
        line = line.strip()
        if len(line) < 5 or len(line) > 80:
            continue
        if _SKIP_LINE_RE.search(line):
            continue
        if line.lower() in _SKIP_WORDS:
            continue
        if _NAME_LINE_RE.match(line):
            return line
    return None


def normalize_full_name(full_name: str | None) -> str:
    """
    Для отображения: «Биценко Владислав» → «Владислав Биценко».
    """
    if not full_name or not str(full_name).strip():
        return "Кандидат"

    parts = [p for p in str(full_name).strip().split() if p]
    if len(parts) < 2:
        return parts[0] if parts else "Кандидат"

    if looks_like_surname(parts[0]) and not looks_like_surname(parts[1]):
        ordered = [parts[1], parts[0], *parts[2:]]
        return " ".join(ordered)
    return " ".join(parts)


def parse_candidate_names(
    resume_text: str | None,
    *,
    llm_full_name: str | None = None,
    llm_first_name: str | None = None,
) -> dict[str, str]:
    """Единая точка: текст резюме + опционально ответ LLM."""
    from_resume = parse_name_from_resume_text(resume_text)
    raw = (from_resume or llm_full_name or "").strip()
    if not raw:
        raw = "Кандидат"

    full_name = normalize_full_name(raw)
    first_name = extract_first_name(raw)
    if llm_first_name and " " not in str(llm_first_name).strip():
        first_name = str(llm_first_name).strip()
    else:
        first_name = extract_first_name(full_name)

    return {"full_name": full_name, "first_name": first_name}
