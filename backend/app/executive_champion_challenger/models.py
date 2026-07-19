from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CandidateRole(str, Enum):
    CHAMPION = "champion"
    CHALLENGER = "challenger"
    RETIRED = "retired"


class EvaluationDecision(str, Enum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    KEEP_CHAMPION = "keep_champion"
    PROMOTION_RECOMMENDED = "promotion_recommended"
    REJECT_CHALLENGER = "reject_challenger"


class StrategyEvidence(BaseModel):
    sample_size: int = Field(ge=0)
    win_rate: float = Field(ge=0, le=1)
    average_r: float
    expectancy_r: float
    profit_factor: float = Field(ge=0)
    max_drawdown_pct: float = Field(ge=0, le=100)
    confidence_calibration_error: float = Field(ge=0, le=1)


class StrategyCandidateCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    account_profile_id: str = Field(min_length=1, max_length=100)
    strategy_id: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=50)
    experiment_id: UUID | None = None
    role: CandidateRole
    evidence: StrategyEvidence
    actor_id: str = Field(min_length=1, max_length=100)


class StrategyCandidate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    account_profile_id: str
    strategy_id: str
    strategy_version: str
    experiment_id: UUID | None = None
    role: CandidateRole
    evidence: StrategyEvidence
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CandidateEvidenceUpdate(BaseModel):
    evidence: StrategyEvidence
    actor_id: str = Field(min_length=1, max_length=100)


class ComparisonPolicy(BaseModel):
    minimum_sample_size: int = Field(default=100, ge=20)
    minimum_profit_factor_uplift: float = Field(default=0.10, ge=0)
    minimum_expectancy_uplift_r: float = Field(default=0.05, ge=0)
    maximum_drawdown_increase_pct: float = Field(default=0.50, ge=0)
    maximum_calibration_error: float = Field(default=0.20, ge=0, le=1)
    required_confidence: float = Field(default=0.95, ge=0.5, le=0.999)


class ComparisonCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    account_profile_id: str = Field(min_length=1, max_length=100)
    champion_id: UUID
    challenger_id: UUID
    policy: ComparisonPolicy = Field(default_factory=ComparisonPolicy)
    actor_id: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def candidates_differ(self) -> "ComparisonCreate":
        if self.champion_id == self.challenger_id:
            raise ValueError("Champion and challenger must differ")
        return self


class StrategyComparison(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    account_profile_id: str
    champion_id: UUID
    challenger_id: UUID
    policy: ComparisonPolicy
    decision: EvaluationDecision
    confidence: float = Field(ge=0, le=1)
    reasons: list[str]
    profit_factor_uplift: float
    expectancy_uplift_r: float
    drawdown_change_pct: float
    created_at: datetime = Field(default_factory=utc_now)


class PromotionRequest(BaseModel):
    comparison_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)


class PromotionResult(BaseModel):
    promoted: bool
    former_champion_id: UUID
    new_champion_id: UUID | None = None
    reason: str


class CandidateListResponse(BaseModel):
    items: list[StrategyCandidate]
    count: int


class ComparisonListResponse(BaseModel):
    items: list[StrategyComparison]
    count: int


class ChampionChallengerStatusResponse(BaseModel):
    workspace_id: str
    candidate_count: int
    comparison_count: int
    autonomous_promotion_enabled: bool = False


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    entity_id: UUID
    details: dict[str, str | int | float | bool | None]
    created_at: datetime = Field(default_factory=utc_now)
