from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class AllocationState(str, Enum):
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
    CONSTRAINT_BREACH = "constraint-breach"
    CONCENTRATION_ALERT = "concentration-alert"
    EFFICIENCY_DECAY = "efficiency-decay"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AllocationCandidate(BaseModel):
    sleeve: str = Field(min_length=1, max_length=120)
    current_weight: float = Field(ge=0, le=1)
    proposed_weight: float = Field(ge=0, le=1)
    expected_return: float
    expected_volatility: float = Field(gt=0)
    expected_shortfall: float = Field(ge=0)
    liquidity_score: float = Field(ge=0, le=100)
    conviction: float = Field(ge=0, le=1)
    confidence: float = Field(default=1, ge=0, le=1)
    freshness: float = Field(default=1, ge=0, le=1)
    provenance: List[str] = Field(default_factory=list)


class AllocationRecordCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=160)
    candidates: List[AllocationCandidate] = Field(min_length=1)
    max_turnover: float = Field(default=0.25, ge=0, le=2)
    max_single_weight: float = Field(default=0.35, gt=0, le=1)
    min_liquidity_score: float = Field(default=50, ge=0, le=100)
    requested_by: str = Field(min_length=1, max_length=120)


class AllocationScores(BaseModel):
    expected_portfolio_return: float
    expected_portfolio_volatility: float
    expected_shortfall: float
    risk_adjusted_efficiency: float
    diversification_score: float
    liquidity_score: float
    turnover: float
    constraint_compliance: float
    confidence: float


class AllocationRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AllocationState
    scores: AllocationScores
    risk_flags: List[str]
    approved_by: Optional[str] = None
    version: int = 1


class AllocationAction(BaseModel):
    action: str = Field(pattern="^(score|submit-review|approve|activate|monitor|suspend|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=120)
    operation_id: str = Field(min_length=1, max_length=160)
    reason: Optional[str] = Field(default=None, max_length=500)
