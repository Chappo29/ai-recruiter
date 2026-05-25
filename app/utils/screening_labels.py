from app.models import Screening

STATUS_LABELS = {
    "pending": "На рассмотрении",
    "forwarded": "Передан дальше",
    "rejected": "Отказ",
}

AI_VERDICT_LABELS = {
    "fit": "Подходит (ИИ)",
    "maybe": "Возможно (ИИ)",
    "reject": "Не подходит (ИИ)",
}


def verdict_label_for(screening: Screening) -> str | None:
    status = (screening.status or "").lower()
    if status in STATUS_LABELS:
        return STATUS_LABELS[status]
    if screening.verdict:
        return AI_VERDICT_LABELS.get(screening.verdict.lower(), screening.verdict)
    return None
