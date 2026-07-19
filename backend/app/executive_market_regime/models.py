from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketRegime(str, Enum):
    strong_trend = "strong_trend"
    weak_trend = "weak_trend"
    range = "range"
    compression = "compression"
    expansion = "expansion"
    accumulation = "accumulation"
    distribution = "distribution"
    manipulation = "manipulation"
    breakout = "breakout"
    pullback = "pullback"
    reversal = "reversal"
    high_volatility = "high_volatility"
    low_volatility = "low_volatility"
    news_driven = "news_driven"
    illiquid = "illiquid"
    transition = "transition"
    unknown = "unknown"


class RegimeDecision(str, Enum):
    allow = "allow"
    shadow_only = "shadow_only"
    block = "block"


class RegimeFeatureSnapshot(BaseModel):
    trend_strength: float = Field(ge=0, le=1)
    volatility_percentile: float = Field(ge=0, le=1)
    range_efficiency: float = Field(ge=0, le=1)
    compression_score: float = Field(ge=0, le=1)
    expansion_score: float = Field(ge=0, le=1)
    liquidity_score: float = Field(ge=0, le=1)
    directional_imbalance: float = Field(ge=-1, le=1)
    volume_confirmation: float = Field(ge=0, le=1)
    news_risk: float = Field(ge=0, le=1)
    session: str = Field(min_length=1, max_length=50)
    killzone_active: bool = False


class RegimePolicy(BaseModel):
    minimum_confidence: float = Field(default=0.65, ge=0, le=1)
    minimum_liquidity: float = Field(default=0.35, ge=0, le=1)
    maximum_news_risk: float = Field(default=0.70, ge=0, le=1)
    shadow_below_confidence: bool = True


class RegimeAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    account_profile_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=30)
    timeframe: str = Field(min_length=1, max_length=20)
    observed_at: datetime = Field(default_factory=utc_now)
    features: RegimeFeatureSnapshot
    policy: RegimePolicy = Field(default_factory=RegimePolicy)
    actor_id: str = Field(min_length=1, max_length=100)


class StrategyRegimeRule(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=100)
    allowed_regimes: list[MarketRegime] = Field(default_factory=list)
    shadow_regimes: list[MarketRegime] = Field(default_factory=list)
    blocked_regimes: list[MarketRegime] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_regime_assignments(self) -> "StrategyRegimeRule":
        groups = self.allowed_regimes + self.shadow_regimes + self.blocked_regimes
        if len(groups) != len(set(groups)):
            raise ValueError("A regime may appear in only one strategy decision group")
        return self


class StrategyRegimeEvaluation(BaseModel):
    strategy_id: str
    decision: RegimeDecision
    reason: str


class MarketRegimeAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    account_profile_id: str
    symbol: str
    timeframe: str
    observed_at: datetime
    primary_regime: MarketRegime
    secondary_regimes: list[MarketRegime] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    tradability: RegimeDecision
    reasons: list[str] = Field(default_factory=list)
    features: RegimeFeatureSnapshot
    policy: RegimePolicy
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)


class RegimeStrategyEvaluationRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    rules: list[StrategyRegimeRule] = Field(min_length=1)
    actor_id: str = Field(min_length=1, max_length=100)


class RegimeStrategyEvaluationResponse(BaseModel):
    assessment_id: UUID
    primary_regime: MarketRegime
    evaluations: list[StrategyRegimeEvaluation]


class RegimeAssessmentListResponse(BaseModel):
    items: list[MarketRegimeAssessment]
    count: int


class RegimeStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_regime: MarketRegime | None
    autonomous_execution_enabled: bool = False


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    entity_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
