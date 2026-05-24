from app.models import Screening


def display_verdict_for(screening: Screening) -> str | None:
    if screening.status == "rejected":
        return "rejected"
    if screening.status == "pending":
        return "pending"
    if screening.status == "failed":
        return "failed"
    return screening.verdict
