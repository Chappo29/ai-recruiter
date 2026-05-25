"""Build vacancy text for LLM prompts in the Telegram bot."""


def build_vacancy_text(
    *,
    title: str,
    company: str | None = None,
    requirements: str | None = None,
    description: str | None = None,
) -> str:
    parts: list[str] = []
    if title:
        parts.append(title)
    if company and company.strip():
        parts.append(f"Компания: {company.strip()}")
    if requirements and requirements.strip():
        parts.append(f"Требования:\n{requirements.strip()}")
    if description and description.strip():
        parts.append(f"Описание:\n{description.strip()}")
    return "\n\n".join(parts) if parts else title or "Вакансия"
