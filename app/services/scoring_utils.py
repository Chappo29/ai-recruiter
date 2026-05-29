"""Deterministic score/verdict/bucket computation (code, not LLM)."""

from __future__ import annotations

from app.core.config import SCORE_FIT_MIN, SCORE_MAYBE_MIN, SCORE_RECOMMENDED_MIN
from app.schemas.llm import DimensionScore, RubricCompetency, ScoreBreakdown, ScoreBreakdownDimension


def verdict_from_score(score: int) -> str:
    if score >= SCORE_FIT_MIN:
        return "fit"
    if score >= SCORE_MAYBE_MIN:
        return "maybe"
    return "reject"


def bucket_from_score(score: int) -> str:
    if score >= SCORE_RECOMMENDED_MIN:
        return "recommended"
    if score >= SCORE_MAYBE_MIN:
        return "review"
    return "weak"


def compute_overall_score(
    dimensions: list[DimensionScore],
    competencies: list[RubricCompetency],
) -> tuple[int, str, bool]:
    """
    Weighted average from 1-5 dimension scores → 0-100.
    Returns (overall_score, bucket, must_have_failed).
    """
    comp_map = {c.id: c for c in competencies}
    if not dimensions:
        return 0, "weak", False

    total_weight = 0.0
    weighted_sum = 0.0
    must_have_failed = False

    for dim in dimensions:
        comp = comp_map.get(dim.competency_id)
        weight = comp.weight if comp else 1.0 / len(dimensions)
        total_weight += weight
        weighted_sum += (dim.score_1_5 / 5.0) * weight
        if comp and comp.must_have and dim.score_1_5 < 3:
            must_have_failed = True

    if total_weight <= 0:
        overall = 0
    else:
        overall = round((weighted_sum / total_weight) * 100)

    if must_have_failed and overall > 49:
        overall = 49

    bucket = bucket_from_score(overall)
    return overall, bucket, must_have_failed


def build_score_breakdown(
    dimensions: list[DimensionScore],
    competencies: list[RubricCompetency],
    overall_score: int,
    bucket: str,
) -> ScoreBreakdown:
    comp_map = {c.id: c for c in competencies}
    breakdown_dims: list[ScoreBreakdownDimension] = []
    for dim in dimensions:
        comp = comp_map.get(dim.competency_id)
        breakdown_dims.append(
            ScoreBreakdownDimension(
                id=dim.competency_id,
                title=comp.title if comp else dim.competency_id,
                score_1_5=dim.score_1_5,
                weight=comp.weight if comp else 0.0,
                evidence=dim.evidence,
            )
        )
    return ScoreBreakdown(bucket=bucket, dimensions=breakdown_dims)
