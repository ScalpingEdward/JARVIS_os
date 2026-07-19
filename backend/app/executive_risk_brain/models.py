from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class RiskState(str, Enum):
    normal = "normal"
    reduced = "reduced"
    frozen = "frozen"
    blocked = "blocked"


class RiskTrend(str, Enum):
    improving = "improving"
    stable = "stable"
    deteriorating = "deteriorating"
    accelerating = "accelerating"


class RiskComponentInput(BaseModel):
    portfolio_heat: float = Field(ge=0, le=100)
    drawdown_risk: float = Field(ge=0, le=100)
    correlation_risk: float = Field(ge=0, le=100)
    concentration_risk: float = Field(ge=0, le=100)
    liquidity_risk: float = Field(ge=0, le=100)
    volatility_risk: float = Field(ge=0, le=100)
    news_risk: float = Field(ge=0, le=100)
    tail_risk: float = Field(ge=0, le=100)
    model_risk: float = Field(ge=0, le=100)
    operational_risk: float = Field(ge=0, le=100)
    confidence_risk: float = Field(ge=0, le=100)


class StrategyRiskInput(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=120)
    symbol: str = Field(min_length=1, max_length=40)
    asset_cluster: str = Field(min_length=1, max_length=80)
    current_weight: float = Field(ge=0, le=1)
    risk_contribution: float = Field(ge=0, le=100)
    adaptive_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    drawdown_pct: float = Field(ge=0, le=100)
    correlation_to_portfolio: float = Field(ge=-1, le=1)


class RiskThresholds(BaseModel):
    reduced_score: float = Field(default=45, ge=0, le=100)
    frozen_score: float = Field(default=65, ge=0, le=100)
    blocked_score: float = Field(default=82, ge=0, le=100)
    max_portfolio_heat: float = Field(default=70, ge=0, le=100)
    max_drawdown_risk: float = Field(default=75, ge=0, le=100)
    max_news_risk: float = Field(default=80, ge=0, le=100)
    max_strategy_risk_contribution: float = Field(default=35, ge=0, le=100)

    @model_validator(mode="after")
    def validate_order(self) -> "RiskThresholds":
        if not self.reduced_score < self.frozen_score < self.blocked_score:
            raise ValueError("Risk score thresholds must be strictly increasing")
        return self


class RiskBrainRunCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    account_profile_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    source_portfolio_run_id: UUID | None = None
    components: RiskComponentInput
    strategies: list[StrategyRiskInput] = Field(default_factory=list, max_length=100)
    previous_global_risk_score: float | None = Field(default=None, ge=0, le=100)
    thresholds: RiskThresholds = Field(default_factory=RiskThresholds)
    source_reference: str | None = Field(default=None, max_length=200)


class StrategyRiskDecision(BaseModel):
    strategy_id: str
    state: RiskState
    risk_score: float
    recommended_weight_multiplier: float
    reasons: list[str]


class RiskMetrics(BaseModel):
    global_risk_score: float
    heat_score: float
    stability_score: float
    survival_score: float
    recovery_score: float
    capital_preservation_score: float
    risk_velocity: float
    forecast_risk_score: float
    risk_trend: RiskTrend


class RiskBrainRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    account_profile_id: str
    actor_id: str
    source_portfolio_run_id: UUID | None = None
    components: RiskComponentInput
    strategy_decisions: list[StrategyRiskDecision]
    metrics: RiskMetrics
    global_state: RiskState
    reasons: list[str]
    source_reference: str | None = None
    autonomous_execution_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskBrainRunListResponse(BaseModel):
    items: list[RiskBrainRun]
    count: int


class RiskBrainStatusResponse(BaseModel):
    workspace_id: str
    module: str = "executive-risk-brain"
    version: str = "18.35"
    runs: int
    autonomous_execution_enabled: bool = False


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    entity_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
