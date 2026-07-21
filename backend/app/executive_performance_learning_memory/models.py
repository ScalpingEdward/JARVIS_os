from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PerformanceLearningState(str, Enum):
    BLOCKED = "blocked"
    ROUTE_EVIDENCE_REQUIRED = "route-evidence-required"
    SAMPLE_INSUFFICIENT = "sample-insufficient"
    DATA_INVALID = "data-invalid"
    DRIFT_DETECTED = "drift-detected"
    DEGRADATION_DETECTED = "degradation-detected"
    REVIEW_REQUIRED = "review-required"
    LEARNING_PENDING = "learning-pending"
    LEARNING_APPROVED = "learning-approved"
    MEMORY_ACTIVE = "memory-active"
    HEALTHY = "healthy"
    FAILED = "failed"


class TradeOutcome(BaseModel):
    trade_id: str = Field(min_length=1, max_length=120)
    strategy_id: str = Field(min_length=1, max_length=120)
    symbol: str = Field(min_length=1, max_length=30)
    account_id: str = Field(min_length=1, max_length=100)
    pnl: float
    risk_amount: float = Field(gt=0)
    planned_rr: float = Field(gt=0)
    realized_rr: float
    holding_seconds: int = Field(ge=0)
    slippage_bps: float = Field(default=0, ge=0)
    regime: str = Field(min_length=1, max_length=50)
    signal_confidence: float = Field(ge=0, le=100)
    routed_by_v19_06: bool = False


class PerformanceLearningCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    upstream_risk_brain_blocked: bool = False
    min_sample_size: int = Field(default=20, ge=1)
    degradation_threshold_pct: float = Field(default=20, gt=0, le=100)
    drift_threshold_pct: float = Field(default=25, gt=0, le=100)
    baseline_win_rate_pct: float = Field(ge=0, le=100)
    baseline_expectancy_r: float
    human_approved: bool = False
    outcomes: list[TradeOutcome] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_trades(self):
        ids = [item.trade_id for item in self.outcomes]
        if len(ids) != len(set(ids)):
            raise ValueError("trade_id values must be unique")
        return self


class PerformanceLearningExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = "approve-learning"
    human_approved: bool | None = None


class StrategyPerformance(BaseModel):
    strategy_id: str
    trades: int
    wins: int
    losses: int
    win_rate_pct: float
    net_pnl: float
    expectancy_r: float
    profit_factor: float
    avg_slippage_bps: float
    avg_holding_seconds: float
    confidence_calibration_error: float


class LearningRecommendation(BaseModel):
    strategy_id: str
    action: str
    reason: str
    risk_multiplier: float = Field(ge=0, le=1.5)


class PerformanceLearningRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: PerformanceLearningState
    detail: str
    request: PerformanceLearningCreate
    portfolio_win_rate_pct: float = 0
    portfolio_expectancy_r: float = 0
    portfolio_profit_factor: float = 0
    max_drawdown: float = 0
    strategies: list[StrategyPerformance] = Field(default_factory=list)
    recommendations: list[LearningRecommendation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PerformanceLearningStatus(BaseModel):
    module: str = "executive-performance-learning-memory"
    version: str = "19.07"
    workspace_id: str
    total_records: int
    active_records: int
    blocked_records: int


class PerformanceLearningAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: PerformanceLearningState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
