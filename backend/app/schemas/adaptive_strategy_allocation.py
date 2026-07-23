from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class StrategyAllocationState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    SCORED = "scored"
    POLICY_READY = "policy-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    STABLE = "stable"
    ALPHA_DECAY = "alpha-decay"
    REGIME_MISMATCH = "regime-mismatch"
    CORRELATION_ALERT = "correlation-alert"
    RETIREMENT_CANDIDATE = "retirement-candidate"
    RECOVERY_CANDIDATE = "recovery-candidate"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class StrategyObservation(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=120)
    regime: str = Field(min_length=1, max_length=80)
    expected_return: float
    realized_return: float
    volatility: float = Field(ge=0)
    downside_deviation: float = Field(ge=0)
    max_drawdown: float = Field(ge=0, le=1)
    win_rate: float = Field(ge=0, le=1)
    profit_factor: float = Field(ge=0)
    alpha_persistence: float = Field(ge=0, le=1)
    regime_fit: float = Field(ge=0, le=1)
    average_correlation: float = Field(ge=-1, le=1)
    liquidity_score: float = Field(ge=0, le=1)
    turnover_rate: float = Field(ge=0)
    current_weight: float = Field(ge=0, le=1)
    confidence: float = Field(default=1, ge=0, le=1)
    freshness: float = Field(default=1, ge=0, le=1)
    provenance: List[str] = Field(default_factory=list)


class StrategyAllocationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=160)
    observations: List[StrategyObservation] = Field(min_length=1)
    max_strategy_weight: float = Field(default=0.35, gt=0, le=1)
    max_turnover: float = Field(default=0.40, ge=0)
    requested_by: str = Field(min_length=1, max_length=120)


class StrategyRecommendation(BaseModel):
    strategy_id: str
    health_score: float
    regime_fit_score: float
    risk_adjusted_score: float
    alpha_decay_score: float
    recommended_weight: float
    lifecycle_signal: str


class StrategyAllocationScores(BaseModel):
    portfolio_strategy_health: float
    regime_alignment: float
    diversification_quality: float
    alpha_persistence: float
    risk_budget_efficiency: float
    turnover_requirement: float
    confidence: float


class StrategyAllocationRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: StrategyAllocationState
    scores: StrategyAllocationScores
    recommendations: List[StrategyRecommendation]
    risk_flags: List[str]
    approved_by: Optional[str] = None
    version: int = 1


class StrategyAllocationAction(BaseModel):
    action: str = Field(pattern="^(score|submit-review|approve|activate|monitor|suspend|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=120)
    operation_id: str = Field(min_length=1, max_length=160)
    reason: Optional[str] = Field(default=None, max_length=500)
