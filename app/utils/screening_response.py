from collections import defaultdict
from uuid import UUID

from app.models import Candidate, Screening, Vacancy
from app.schemas.llm import ScoreBreakdown
from app.schemas.screening import ScreeningCandidateBrief, ScreeningResponse
from app.utils.display_verdict import display_verdict_for
from app.utils.name import normalize_full_name
from app.utils.screening_labels import verdict_label_for
from app.services.screening_service import score_breakdown_for_screening


def compute_screening_indices(screenings: list[Screening]) -> dict[UUID, int]:
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
    vacancy: Vacancy | None = None,
    screening_index: int | None = None,
    score_breakdown: ScoreBreakdown | None = None,
) -> ScreeningResponse:
    cand = candidate
    vac = vacancy
    if vac is None and screening.vacancy is not None:
        vac = screening.vacancy

    raw_name = cand.full_name if cand else None
    display_name = normalize_full_name(raw_name) if raw_name else None
    candidate_brief = None
    avatar_url = None
    resume_url = None
    if cand is not None:
        if cand.avatar_file_path:
            avatar_url = f"/candidates/{cand.id}/avatar"
        if cand.resume_file_path:
            resume_url = f"/candidates/{cand.id}/resume"
        candidate_brief = ScreeningCandidateBrief.model_validate(cand).model_copy(
            update={
                **({"full_name": display_name} if display_name else {}),
                **({"avatar_file_path": avatar_url} if avatar_url else {}),
            }
        )

    return ScreeningResponse.model_validate(screening).model_copy(
        update={
            "vacancy_title": vac.title if vac else None,
            "candidate": candidate_brief,
            "candidate_name": display_name,
            "candidate_telegram_id": cand.telegram_id if cand else None,
            "resume_text": cand.resume_text if cand else None,
            "resume_file_path": resume_url,
            "avatar_file_path": avatar_url,
            "avatar_url": avatar_url,
            "resume_url": resume_url,
            "display_verdict": display_verdict_for(screening),
            "verdict_label": verdict_label_for(screening),
            "screening_index": screening_index,
            "score_breakdown": score_breakdown
            or score_breakdown_for_screening(screening),
        }
    )
