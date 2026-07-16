from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class TwinDomain(StrEnum):
    trading = "trading"
    business = "business"
    engineering = "engineering"
    research = "research"
    finance = "finance"
    health = "health"
    legal = "legal"
    personal = "personal"


class RiskPosture(StrEnum):
    conservative = "conservative"
    balanced = "balanced"
    assertive = "assertive"


class FeedbackSignal(StrEnum):
    accepted = "accepted"
    rejected = "rejected"
    modified = "modified"
    neutral = "neutral"


class TwinGoal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    domain: TwinDomain
    title: str = Field(min_length=2, max_length=200)
    target: str = Field(min_length=2, max_length=1000)
    priority: int = Field(default=50, ge=0, le=100)
    active: bool = True


class TwinProfileCreate(BaseModel):
    owner_name: str = Field(default="MASTER Brano", min_length=2, max_length=80)
    risk_posture: RiskPosture = RiskPosture.balanced
    decision_speed: int = Field(default=65, ge=0, le=100)
    evidence_threshold: float = Field(default=0.72, ge=0, le=1)
    autonomy_limit: int = Field(default=20, ge=0, le=100)
    preferences: dict[str, str | int | float | bool] = Field(default_factory=dict)
    goals: list[TwinGoal] = Field(default_factory=list)


class TwinProfile(TwinProfileCreate):
    id: UUID = Field(default_factory=uuid4)
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    learned_feedback_count: int = 0
    automatic_execution: bool = False


class ScenarioOption(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2, max_length=2000)
    domain: TwinDomain
    expected_value: float = Field(default=0.5, ge=0, le=1)
    risk: float = Field(default=0.5, ge=0, le=1)
    reversibility: float = Field(default=0.5, ge=0, le=1)
    evidence_quality: float = Field(default=0.5, ge=0, le=1)
    time_pressure: float = Field(default=0.5, ge=0, le=1)
    requires_approval: bool = True
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class ScenarioRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    options: list[ScenarioOption] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def unique_option_ids(self) -> "ScenarioRequest":
        if len({option.id for option in self.options}) != len(self.options):
            raise ValueError("Scenario option IDs must be unique")
        return self


class ScenarioScore(BaseModel):
    option_id: UUID
    title: str
    score: float = Field(ge=0, le=1)
    fit: float = Field(ge=0, le=1)
    risk_adjustment: float = Field(ge=0, le=1)
    evidence_adjustment: float = Field(ge=0, le=1)
    reasons: list[str]


class TwinRecommendation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    profile_id: UUID
    question: str
    recommended_option_id: UUID
    recommended_title: str
    confidence: float = Field(ge=0, le=1)
    explanation: str
    scores: list[ScenarioScore]
    requires_human_approval: bool = True
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    automatic_execution: bool = False


class TwinFeedbackCreate(BaseModel):
    recommendation_id: UUID
    signal: FeedbackSignal
    selected_option_id: UUID | None = None
    note: str | None = Field(default=None, max_length=2000)
    allow_learning: bool = False


class TwinFeedback(TwinFeedbackCreate):
    id: UUID = Field(default_factory=uuid4)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    applied_to_profile: bool = False


class TwinStatus(BaseModel):
    configured: bool
    owner_name: str
    profile_version: int
    goals: int
    recommendations: int
    feedback_items: int
    learning_enabled_only_by_consent: bool = True
    automatic_execution: bool = False
    automatic_order_execution: bool = False
    automatic_merge: bool = False
