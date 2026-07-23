from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class ScenarioState(str, Enum):
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
    SCENARIO_BREACH = "scenario-breach"
    REBALANCE_PRESSURE = "rebalance-pressure"
    RESILIENCE_DECAY = "resilience-decay"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class ScenarioShock(BaseModel):
    factor: str = Field(min_length=1, max_length=120)
    shock_pct: float = Field(ge=-1, le=1)
    probability: float = Field(ge=0, le=1)
    liquidity_multiplier: float = Field(default=1, gt=0, le=10)
    volatility_multiplier: float = Field(default=1, gt=0, le=10)
    correlation_shift: float = Field(default=0, ge=-1, le=1)
    confidence: float = Field(default=1, ge=0, le=1)
    freshness: float = Field(default=1, ge=0, le=1)
    provenance: List[str] = Field(default_factory=list)


class PortfolioSleeve(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    current_weight: float = Field(ge=0, le=1)
    target_weight: float = Field(ge=0, le=1)
    expected_return_pct: float = Field(ge=-1, le=1)
    volatility_pct: float = Field(ge=0, le=2)
    liquidity_score: float = Field(ge=0, le=100)
    factor_sensitivities: dict[str, float] = Field(default_factory=dict)


class ScenarioRecordCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=160)
    portfolio_value: float = Field(gt=0)
    max_acceptable_loss_pct: float = Field(gt=0, le=1)
    max_turnover_pct: float = Field(gt=0, le=1)
    sleeves: List[PortfolioSleeve] = Field(min_length=1)
    shocks: List[ScenarioShock] = Field(min_length=1)
    requested_by: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_weights(self) -> "ScenarioRecordCreate":
        current = sum(item.current_weight for item in self.sleeves)
        target = sum(item.target_weight for item in self.sleeves)
        if abs(current - 1) > 0.01 or abs(target - 1) > 0.01:
            raise ValueError("current and target sleeve weights must each sum to 1")
        return self


class ScenarioScores(BaseModel):
    expected_scenario_loss_pct: float
    tail_scenario_loss_pct: float
    probability_weighted_loss_pct: float
    rebalancing_pressure: float
    turnover_requirement_pct: float
    liquidity_resilience: float
    correlation_resilience: float
    portfolio_resilience: float
    recommendation_confidence: float


class ScenarioRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: ScenarioState
    scores: ScenarioScores
    recommended_weights: dict[str, float]
    risk_flags: List[str]
    approved_by: Optional[str] = None
    version: int = 1


class ScenarioAction(BaseModel):
    action: str = Field(pattern="^(score|submit-review|approve|activate|monitor|suspend|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=120)
    operation_id: str = Field(min_length=1, max_length=160)
    reason: Optional[str] = Field(default=None, max_length=500)
