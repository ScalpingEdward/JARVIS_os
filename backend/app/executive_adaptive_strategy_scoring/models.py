from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ScoreDecision(str, Enum):
    eligible = "eligible"
    shadow_only = "shadow_only"
    blocked = "blocked"


class ConfidenceBand(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"
    very_high = "very_high"


class ScoringWeights(BaseModel):
    regime_match: float = Field(default=0.20, ge=0, le=1)
    evidence: float = Field(default=0.25, ge=0, le=1)
    shadow_performance: float = Field(default=0.10, ge=0, le=1)
    champion_status: float = Field(default=0.05, ge=0, le=1)
    risk_quality: float = Field(default=0.15, ge=0, le=1)
    market_quality: float = Field(default=0.10, ge=0, le=1)
    recency_stability: float = Field(default=0.10, ge=0, le=1)
    calibration: float = Field(default=0.05, ge=0, le=1)

    @model_validator(mode="after")
    def validate_total(self):
        total = sum(self.model_dump().values())
        if abs(total - 1.0) > 0.001:
            raise ValueError("Scoring weights must sum to 1.0")
        return self


class StrategyScoreInput(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=50)
    is_champion: bool = False
    regime_match: float = Field(ge=0, le=1)
    evidence_score: float = Field(ge=0, le=1)
    evidence_sample_size: int = Field(ge=0)
    shadow_score: float = Field(default=0.5, ge=0, le=1)
    profit_factor: float = Field(default=1.0, ge=0)
    expectancy_r: float = Field(default=0.0, ge=-10, le=10)
    max_drawdown_pct: float = Field(default=0.0, ge=0, le=100)
    liquidity_score: float = Field(default=1.0, ge=0, le=1)
    volatility_fit: float = Field(default=0.5, ge=0, le=1)
    news_risk: float = Field(default=0.0, ge=0, le=1)
    spread_quality: float = Field(default=1.0, ge=0, le=1)
    recent_performance: float = Field(default=0.5, ge=0, le=1)
    stability_score: float = Field(default=0.5, ge=0, le=1)
    calibration_score: float = Field(default=0.5, ge=0, le=1)
    regime_permission: ScoreDecision = ScoreDecision.eligible


class ScoringRunCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    account_profile_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=30)
    timeframe: str = Field(min_length=1, max_length=20)
    market_regime: str = Field(min_length=1, max_length=80)
    actor_id: str = Field(min_length=1, max_length=100)
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    strategies: list[StrategyScoreInput] = Field(min_length=1, max_length=100)
    minimum_evidence_sample: int = Field(default=30, ge=1)
    minimum_eligible_score: float = Field(default=65.0, ge=0, le=100)
    minimum_shadow_score: float = Field(default=45.0, ge=0, le=100)
    maximum_news_risk: float = Field(default=0.75, ge=0, le=1)
    maximum_drawdown_pct: float = Field(default=15.0, ge=0, le=100)


class ScoreBreakdown(BaseModel):
    regime_match: float
    evidence: float
    shadow_performance: float
    champion_status: float
    risk_quality: float
    market_quality: float
    recency_stability: float
    calibration: float


class StrategyScoreResult(BaseModel):
    strategy_id: str
    strategy_version: str
    final_score: float
    rank: int = 0
    decision: ScoreDecision
    confidence_band: ConfidenceBand
    breakdown: ScoreBreakdown
    reasons: list[str]


class ScoringRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    account_profile_id: str
    symbol: str
    timeframe: str
    market_regime: str
    actor_id: str
    weights: ScoringWeights
    results: list[StrategyScoreResult]
    winner_strategy_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScoringRunListResponse(BaseModel):
    items: list[ScoringRun]
    count: int


class AdaptiveScoringStatusResponse(BaseModel):
    workspace_id: str
    module: str = "executive_adaptive_strategy_scoring"
    version: str = "18.33"
    scoring_runs: int
    autonomous_execution: bool = False


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    entity_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
