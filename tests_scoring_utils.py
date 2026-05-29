"""
Deterministic scoring utils tests (PR #3).
Run: python tests_scoring_utils.py
"""

from app.schemas.llm import DimensionScore, RubricCompetency
from app.services.scoring_utils import compute_overall_score


def test_weighted_average() -> None:
    comps = [
        RubricCompetency(id="a", title="A", weight=0.5, must_have=False, levels={}),
        RubricCompetency(id="b", title="B", weight=0.5, must_have=False, levels={}),
    ]
    dims = [
        DimensionScore(competency_id="a", score_1_5=5, evidence=[], flags=[]),
        DimensionScore(competency_id="b", score_1_5=1, evidence=[], flags=[]),
    ]
    score, bucket, must_fail = compute_overall_score(dims, comps)
    assert score == 60
    assert must_fail is False
    assert bucket in ("recommended", "review", "weak")


def test_must_have_caps_score() -> None:
    comps = [
        RubricCompetency(id="hard", title="Hard", weight=1.0, must_have=True, levels={}),
    ]
    dims = [
        DimensionScore(competency_id="hard", score_1_5=1, evidence=[], flags=[]),
    ]
    score, bucket, must_fail = compute_overall_score(dims, comps)
    assert must_fail is True
    assert score <= 49
    assert bucket in ("review", "weak")


def main() -> int:
    test_weighted_average()
    test_must_have_caps_score()
    print("scoring utils tests ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

