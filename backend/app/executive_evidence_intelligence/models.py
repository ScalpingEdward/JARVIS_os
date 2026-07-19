from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class EvidenceSource(str, Enum):
    SHADOW_TRADE = "shadow_trade"
    BACKTEST = "backtest"
    PAPER_TRADE = "paper_trade"
    LIVE_OBSERVATION = "live_observation"
    MANUAL_RESEARCH = "manual_research"


class EvidenceVerdict(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    INSUFFICIENT = "insufficient"


class ReliabilityBand(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class EvidenceContext(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=50)
    account_profile: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=30)
    timeframe: str = Field(min_length=1, max_length=20)
    market_regime: str = Field(min_length=1, max_length=50)
    session: str = Field(min_length=1, max_length=50)
    killzone: str | None = Field(default=None, max_length=50)
    weekday: int = Field(ge=0, le=6)
    news_risk: float = Field(ge=0.0, le=1.0)
    factors: dict[str, str | float | int | bool] = Field(default_factory=dict)


class EvidenceObservationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    source: EvidenceSource
    source_reference: str = Field(min_length=1, max_length=200)
    context: EvidenceContext
    realized_r: float = Field(ge=-100.0, le=100.0)
    won: bool
    confidence_at_decision: float = Field(ge=0.0, le=1.0)
    max_favorable_excursion_r: float | None = Field(default=None, ge=0.0, le=100.0)
    max_adverse_excursion_r: float | None = Field(default=None, ge=0.0, le=100.0)
    notes: str | None = Field(default=None, max_length=1000)


class EvidenceObservation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    source: EvidenceSource
    source_reference: str
    context: EvidenceContext
    realized_r: float
    won: bool
    confidence_at_decision: float
    max_favorable_excursion_r: float | None = None
    max_adverse_excursion_r: float | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceQuery(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    strategy_id: str | None = Field(default=None, max_length=100)
    account_profile: str | None = Field(default=None, max_length=100)
    symbol: str | None = Field(default=None, max_length=30)
    timeframe: str | None = Field(default=None, max_length=20)
    market_regime: str | None = Field(default=None, max_length=50)
    session: str | None = Field(default=None, max_length=50)
    factor_filters: dict[str, str | float | int | bool] = Field(default_factory=dict)
    minimum_sample: int = Field(default=30, ge=1, le=100000)


class EvidenceMetrics(BaseModel):
    sample_size: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    average_r: float = 0.0
    expectancy_r: float = 0.0
    profit_factor: float | None = None
    average_mfe_r: float | None = None
    average_mae_r: float | None = None
    confidence_calibration_error: float = 0.0
    standard_error_r: float | None = None


class EvidenceAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    query: EvidenceQuery
    metrics: EvidenceMetrics
    verdict: EvidenceVerdict
    reliability: ReliabilityBand
    evidence_score: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceComparisonCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    baseline_query: EvidenceQuery
    candidate_query: EvidenceQuery
    minimum_sample: int = Field(default=50, ge=1, le=100000)
    minimum_expectancy_edge_r: float = Field(default=0.10, ge=0.0, le=20.0)
    maximum_calibration_degradation: float = Field(default=0.05, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_workspace_alignment(self) -> "EvidenceComparisonCreate":
        if self.baseline_query.workspace_id != self.workspace_id or self.candidate_query.workspace_id != self.workspace_id:
            raise ValueError("Comparison queries must belong to the request workspace")
        return self


class EvidenceComparison(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    baseline: EvidenceAssessment
    candidate: EvidenceAssessment
    candidate_edge_r: float
    recommendation: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceStatusResponse(BaseModel):
    workspace_id: str
    observation_count: int
    assessment_count: int
    comparison_count: int
    autonomous_execution_enabled: bool = False


class EvidenceObservationListResponse(BaseModel):
    items: list[EvidenceObservation]
    count: int


class EvidenceAssessmentListResponse(BaseModel):
    items: list[EvidenceAssessment]
    count: int


class EvidenceComparisonListResponse(BaseModel):
    items: list[EvidenceComparison]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    entity_type: str
    entity_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
