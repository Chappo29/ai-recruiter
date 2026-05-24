from collections import defaultdict
from uuid import UUID

from app.models import Candidate, Screening
from app.schemas.screening import ScreeningCandidateBrief, ScreeningResponse
from app.utils.display_verdict import display_verdict_for
from app.utils.screening_labels import verdict_label_for


def compute_screening_indices(screenings: list[Screening]) -> dict[UUID, int]:
    """Attempt number per candidate per vacancy (1 = first, 2 = second, …)."""
    by_pair: dict[tuple[UUID, UUID], list[Screening]] = defaultdict(list)
    for screening in screenings:
        by_pair[(screening.vacancy_id, screening.candidate_id)].append(screening)

    indices: dict[UUID, int] = {}
    for group in by_pair.values():
        ordered = sorted(group, key=lambda s: s.created_at)
        for attempt, screening in enumerate(ordered, start=1):
            indices[screening.id] = attempt
    return indices


def to_screening_response(
    screening: Screening,
    *,
    candidate: Candidate | None = None,
    screening_index: int | None = None,
) -> ScreeningResponse:
    cand = candidate
    full_name = cand.full_name if cand else None
    candidate_brief = (
        ScreeningCandidateBrief.model_validate(cand) if cand is not None else None
    )
    display_verdict = display_verdict_for(screening)
    return ScreeningResponse.model_validate(screening).model_copy(
        update={
            "candidate": candidate_brief,
            "candidate_name": full_name,
            "candidate_telegram_id": cand.telegram_id if cand else None,
            "resume_text": cand.resume_text if cand else None,
            "resume_file_path": cand.resume_file_path if cand else None,
            "avatar_file_path": cand.avatar_file_path if cand else None,
            "display_verdict": display_verdict,
            "verdict_label": verdict_label_for(screening),
            "screening_index": screening_index,
        }
    )
