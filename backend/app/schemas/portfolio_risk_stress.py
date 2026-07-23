from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class PortfolioRiskState(str, Enum):
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
    CONCENTRATION_ALERT = "concentration-alert"
    STRESS_BREACH = "stress-breach"
    DRAWDOWN_ALERT = "drawdown-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class PortfolioRiskObservation(BaseModel):
    sleeve: str = Field(min_length=1, max_length=120)
    asset_class: str = Field(min_length=1, max_length=80)
    market_value: float = Field(gt=0)
    weight: float = Field(ge=0, le=1)
    volatility: float = Field(ge=0)
    beta: float
    liquidity_days: float = Field(ge=0)
    expected_shortfall_pct: float = Field(ge=0)
    stress_loss_pct: float = Field(ge=0)
    drawdown_pct: float = Field(ge=0)
    correlation_cluster: str = Field(min_length=1, max_length=120)
    confidence: float = Field(default=1, ge=0, le=1)
    freshness: float = Field(default=1, ge=0, le=1)
    provenance: List[str] = Field(default_factory=list)


class PortfolioRiskRecordCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=160)
    observations: List[PortfolioRiskObservation] = Field(min_length=1)
    requested_by: str = Field(min_length=1, max_length=120)


class PortfolioRiskScores(BaseModel):
    concentration_risk: float
    expected_shortfall_pct: float
    stress_loss_pct: float
    drawdown_pressure: float
    liquidity_risk: float
    correlation_risk: float
    risk_resilience: float
    confidence: float


class PortfolioRiskRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: PortfolioRiskState
    scores: PortfolioRiskScores
    risk_flags: List[str]
    approved_by: Optional[str] = None
    version: int = 1


class PortfolioRiskAction(BaseModel):
    action: str = Field(pattern="^(score|submit-review|approve|activate|monitor|suspend|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=120)
    operation_id: str = Field(min_length=1, max_length=160)
    reason: Optional[str] = Field(default=None, max_length=500)
