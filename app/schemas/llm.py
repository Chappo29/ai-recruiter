"""Pydantic schemas for LLM JSON responses."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AIMarkers(BaseModel):
    suspected: bool = False
    confidence: Literal["low", "medium", "high"] = "low"
    reasons: list[str] = Field(default_factory=list)


class ScreeningLLMResult(BaseModel):
    """Legacy single-call screening response."""

    verdict: str | None = None
    score: int | None = None
    summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    ai_markers: AIMarkers = Field(default_factory=AIMarkers)
    red_flags: list[str] = Field(default_factory=list)
    verification_questions: list[str] = Field(default_factory=list)

    @field_validator("score")
    @classmethod
    def clamp_score(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return int(max(0, min(100, int(value))))


class CompetencyLevel(BaseModel):
    levels: dict[str, str] = Field(default_factory=dict)


class RubricCompetency(BaseModel):
    id: str
    title: str
    weight: float = 0.2
    must_have: bool = False
    levels: dict[str, str] = Field(default_factory=dict)


class RubricDraft(BaseModel):
    competencies: list[RubricCompetency] = Field(default_factory=list)
    generated_from: dict[str, Any] = Field(default_factory=dict)


class ExtractedProfile(BaseModel):
    """Structured resume profile extracted from raw text."""

    skills: list[str] = Field(default_factory=list)
    experience_years: float | None = None
    roles: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    summary: str = ""

    @field_validator("skills", "roles", "industries", "achievements", "education", "tools", "gaps", mode="before")
    @classmethod
    def none_to_list(cls, value):  # type: ignore[no-untyped-def]
        if value is None:
            return []
        return value


class DimensionScore(BaseModel):
    competency_id: str
    score_1_5: int = Field(ge=1, le=5)
    evidence: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)


class DimensionScoreResult(BaseModel):
    dimensions: list[DimensionScore] = Field(default_factory=list)
    summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    verification_questions: list[str] = Field(default_factory=list)
    ai_markers: AIMarkers = Field(default_factory=AIMarkers)


class BotInterviewTurn(BaseModel):
    message: str = ""
    done: bool = False


class AnswerEvaluation(BaseModel):
    score_1_5: int = Field(ge=1, le=5, default=3)
    evidence: list[str] = Field(default_factory=list)
    summary: str = ""


class ScoreBreakdownDimension(BaseModel):
    id: str
    title: str | None = None
    score_1_5: int
    weight: float
    evidence: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    bucket: Literal["recommended", "review", "weak"]
    dimensions: list[ScoreBreakdownDimension] = Field(default_factory=list)
