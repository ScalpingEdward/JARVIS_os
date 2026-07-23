from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class AttributionState(str, Enum):
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
    RISK_DRIFT = "risk-drift"
    BENCHMARK_DIVERGENCE = "benchmark-divergence"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AttributionObservation(BaseModel):
    sleeve: str = Field(min_length=1, max_length=120)
    asset_class: str = Field(min_length=1, max_length=80)
    strategy: str = Field(min_length=1, max_length=120)
    portfolio_return: float = Field(ge=-1, le=10)
    benchmark_return: float = Field(ge=-1, le=10)
    weight: float = Field(ge=0, le=1)
    active_risk: float = Field(default=0, ge=0)
    drawdown: float = Field(default=0, ge=0, le=1)
    turnover: float = Field(default=0, ge=0)
    transaction_cost_bps: float = Field(default=0, ge=0)
    confidence: float = Field(default=1, ge=0, le=1)
    freshness: float = Field(default=1, ge=0, le=1)
    provenance: List[str] = Field(default_factory=list)


class AttributionRecordCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=160)
    observations: List[AttributionObservation] = Field(min_length=1)
    requested_by: str = Field(min_length=1, max_length=120)


class AttributionScores(BaseModel):
    total_return: float
    benchmark_return: float
    active_return: float
    allocation_effect: float
    selection_effect: float
    cost_drag_bps: float
    risk_efficiency: float
    drawdown_resilience: float
    alpha_persistence: float
    confidence: float


class AttributionRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AttributionState
    scores: AttributionScores
    risk_flags: List[str]
    approved_by: Optional[str] = None
    version: int = 1


class AttributionAction(BaseModel):
    action: str = Field(pattern="^(score|submit-review|approve|activate|monitor|suspend|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=120)
    operation_id: str = Field(min_length=1, max_length=160)
    reason: Optional[str] = Field(default=None, max_length=500)
