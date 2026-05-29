"""Защита от prompt injection и валидация пользовательского ввода."""

import re

# Паттерны prompt injection атак
INJECTION_PATTERNS = [
    r'ignore\s+(previous|all)\s+(instructions|prompts?|rules?)',
    r'(представь|imagine|pretend|act\s+as|you\s+are\s+now)\s+(что\s+)?ты',
    r'(forget|игнорируй|забудь)\s+(everything|все|всё)',
    r'system:?\s*',
    r'<\|.*?\|>',  # Special tokens
    r'\[INST\]|\[/INST\]',  # Llama instruction tokens
    r'###\s*(system|user|assistant)',
    r'new\s+(role|task|instruction)',
    r'override\s+(previous|default)',
    r'теперь\s+ты\s+(должен|будешь)',
    r'дай\s+мне\s+(правильный|лучший)\s+ответ',
    r'напиши\s+(за\s+меня|мне\s+код|мне\s+текст)',
    r'simulate|эмулируй',
]

# Мат и оскорбления (базовый список)
PROFANITY_PATTERNS = [
    r'\b(пошел|иди)\s+(нахуй|в\s+жопу|к\s+черту)',
    r'\b(нахуй|похуй|хуй|хуя|хуев|хуевый)',
    r'\b(блядь|бля|блять|блядский)',
    r'\b(ебать|ебал|ебет|ебаный|еб[ао]ть)',
    r'\b(пизда|пиздец|пиздить)',
    r'\b(сука|суки|сучий)',
    r'\b(дебил|дебилы|идиот|идиоты|мудак|мудаки)',
    r'\b(говно|гов[нк]о|говнище)',
]

# Компиляция регулярок
INJECTION_REGEX = re.compile(
    '|'.join(f'({pattern})' for pattern in INJECTION_PATTERNS),
    re.IGNORECASE | re.UNICODE
)

PROFANITY_REGEX = re.compile(
    '|'.join(f'({pattern})' for pattern in PROFANITY_PATTERNS),
    re.IGNORECASE | re.UNICODE
)

# Подозрительные фразы (более мягкая проверка)
SUSPICIOUS_PHRASES = [
    'ты senior',
    'ты эксперт',
    'ты профессионал',
    'помоги мне',
    'научи меня',
    'объясни как',
    'расскажи мне',
]


def sanitize_candidate_message(message: str, max_length: int = 500) -> str:
    """
    Очищает и валидирует сообщение кандидата.
    
    Args:
        message: Сообщение от кандидата
        max_length: Максимальная длина (защита от spam)
    
    Returns:
        Очищенное сообщение
    
    Raises:
        ValueError: Если обнаружена попытка prompt injection
    """
    if not message or not isinstance(message, str):
        return ""
    
    # Обрезаем до максимальной длины
    message = message[:max_length].strip()
    
    # Проверка на мат и оскорбления
    if PROFANITY_REGEX.search(message):
        return "[PROFANITY_DETECTED]"
    
    # Проверка на prompt injection
    if INJECTION_REGEX.search(message):
        # Заменяем опасные инструкции на безопасный текст
        return "[Кандидат пытался дать инструкции боту - игнорируем и возвращаемся к вопросам]"
    
    # Проверка на подозрительные фразы (более мягко)
    lower_msg = message.lower()
    suspicious_count = sum(1 for phrase in SUSPICIOUS_PHRASES if phrase in lower_msg)
    
    if suspicious_count >= 2:
        # Если много подозрительных фраз - скорее всего manipulation
        return "[Кандидат написал подозрительный текст - возвращаемся к вопросам по вакансии]"
    
    return message


def is_answer_too_short(message: str, min_length: int = 2) -> bool:
    """Проверка что ответ не слишком короткий (но допускаем 'да', 'нет')."""
    return len(message.strip()) < min_length


def contains_non_russian(message: str) -> bool:
    """Проверка наличия нерусских символов (кроме латиницы, цифр, пунктуации)."""
    # Разрешаем: кириллицу, латиницу, цифры, пробелы, базовую пунктуацию
    allowed_pattern = re.compile(r'^[а-яёА-ЯЁa-zA-Z0-9\s\.,!?\-:;()"\'\n]+$', re.UNICODE)
    
    # Если есть китайские, арабские и другие символы - вернем True
    return not allowed_pattern.match(message) if message else False


def validate_and_clean_candidate_input(
    message: str,
    *,
    max_length: int = 500,
    check_injection: bool = True,
) -> dict:
    """
    Полная валидация и очистка ввода кандидата.
    
    Returns:
        {
            "cleaned": str,  # Очищенное сообщение
            "is_safe": bool,  # Безопасно ли
            "warning": str | None,  # Предупреждение (если есть)
        }
    """
    if not message:
        return {
            "cleaned": "",
            "is_safe": True,
            "warning": None,
        }
    
    original_len = len(message)
    warning = None
    
    # Обрезка
    if original_len > max_length:
        message = message[:max_length]
        warning = "Ответ слишком длинный, обрезан"
    
    # Проверка на injection
    if check_injection:
        cleaned = sanitize_candidate_message(message, max_length=max_length)
        if cleaned.startswith("[Кандидат"):
            # Обнаружена атака
            return {
                "cleaned": cleaned,
                "is_safe": False,
                "warning": "Обнаружена попытка manipulation",
            }
        message = cleaned
    
    # Проверка на нерусские символы (кроме английского)
    if contains_non_russian(message):
        # Оставляем как есть, но помечаем
        warning = "Содержит нестандартные символы"
    
    return {
        "cleaned": message,
        "is_safe": True,
        "warning": warning,
    }


def sanitize_resume_for_llm(resume_text: str, *, max_length: int = 12000) -> str:
    """Strip prompt-injection patterns from resume text before LLM screening."""
    if not resume_text:
        return ""
    text = resume_text[:max_length]
    if INJECTION_REGEX.search(text):
        text = INJECTION_REGEX.sub("[removed]", text)
    return text.strip()
