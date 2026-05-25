from app.models import Screening

SCREENING_STATUSES = frozenset({"pending", "forwarded", "rejected"})


def display_verdict_for(screening: Screening) -> str | None:
    status = (screening.status or "").lower()
    if status in SCREENING_STATUSES:
        return status
    return screening.verdict
