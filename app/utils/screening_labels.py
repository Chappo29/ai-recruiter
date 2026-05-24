from app.models import Screening

VERDICT_LABELS = {
    "fit": "Подходит",
    "maybe": "На рассмотрении",
    "reject": "Не подходит",
}


def verdict_label_for(screening: Screening) -> str | None:
    if screening.status == "rejected":
        return "Отказ отправлен"
    if screening.status == "pending":
        return "Обработка…"
    if screening.status == "failed":
        return "Ошибка ИИ"
    if screening.verdict:
        return VERDICT_LABELS.get(screening.verdict.lower(), screening.verdict)
    return None
