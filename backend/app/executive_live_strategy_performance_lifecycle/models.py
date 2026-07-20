from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class LifecycleState(str, Enum):
    blocked = "blocked"
    observe = "observe"
    validate = "validate"
    promote = "promote"
    constrain = "constrain"
    pause = "pause"
    retire = "retire"


class StrategyPerformanceInput(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=100)
    broker_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=40)
    market_regime: str = Field(min_length=1, max_length=80)
    allocated_capital: float = Field(gt=0)
    gross_pnl: float
    trading_costs: float = Field(ge=0)
    benchmark_pnl: float = 0
    max_drawdown_share: float = Field(ge=0, le=1)
    risk_share: float = Field(ge=0, le=1)
    win_rate: float = Field(ge=0, le=1)
    profit_factor: float = Field(ge=0)
    sample_trades: int = Field(ge=0)
    regime_fit_score: int = Field(ge=0, le=100)
    execution_quality_score: int = Field(ge=0, le=100)


class LifecyclePolicy(BaseModel):
    minimum_sample_trades: int = Field(default=30, ge=1)
    minimum_profit_factor: float = Field(default=1.15, ge=0)
    minimum_regime_fit_score: int = Field(default=60, ge=0, le=100)
    minimum_execution_quality_score: int = Field(default=70, ge=0, le=100)
    maximum_drawdown_share: float = Field(default=0.10, gt=0, le=1)
    maximum_risk_share: float = Field(default=0.35, gt=0, le=1)
    retire_after_consecutive_failures: int = Field(default=3, ge=1, le=20)


class StrategyLifecycleAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    human_approved: bool = False
    risk_brain_clear: bool = True
    consecutive_failed_reviews: int = Field(default=0, ge=0)
    strategy: StrategyPerformanceInput
    policy: LifecyclePolicy

    @model_validator(mode="after")
    def validate_live_capital(self):
        if self.strategy.allocated_capital <= 0:
            raise ValueError("Owned Live strategy capital must be positive")
        return self


class PerformanceAttribution(BaseModel):
    gross_return_share: float
    net_return_share: float
    benchmark_return_share: float
    alpha_return_share: float
    cost_drag_share: float
    risk_adjusted_alpha: float


class LifecycleScores(BaseModel):
    alpha_quality: int = Field(ge=0, le=100)
    cost_efficiency: int = Field(ge=0, le=100)
    drawdown_safety: int = Field(ge=0, le=100)
    evidence_strength: int = Field(ge=0, le=100)
    regime_resilience: int = Field(ge=0, le=100)
    lifecycle_confidence: int = Field(ge=0, le=100)


class StrategyLifecycleAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    strategy_id: str
    state: LifecycleState
    attribution: PerformanceAttribution
    scores: LifecycleScores
    deployable: bool
    recommended_action: str
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LifecycleStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: LifecycleState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
