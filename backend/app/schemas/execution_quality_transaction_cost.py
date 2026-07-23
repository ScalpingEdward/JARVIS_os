from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ExecutionState(str, Enum):
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
    COST_SHIFT = "cost-shift"
    SLIPPAGE_ALERT = "slippage-alert"
    VENUE_DEGRADATION = "venue-degradation"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class ExecutionObservation(BaseModel):
    venue: str = Field(min_length=1, max_length=120)
    symbol: str = Field(min_length=1, max_length=64)
    side: str = Field(pattern="^(buy|sell)$")
    order_type: str = Field(min_length=1, max_length=40)
    requested_quantity: float = Field(gt=0)
    filled_quantity: float = Field(ge=0)
    arrival_price: float = Field(gt=0)
    average_fill_price: float = Field(gt=0)
    benchmark_price: Optional[float] = Field(default=None, gt=0)
    explicit_fees_bps: float = Field(default=0, ge=0)
    latency_ms: float = Field(default=0, ge=0)
    participation_rate: float = Field(default=0, ge=0, le=1)
    confidence: float = Field(default=1, ge=0, le=1)
    freshness: float = Field(default=1, ge=0, le=1)
    provenance: List[str] = Field(default_factory=list)


class ExecutionRecordCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=160)
    observations: List[ExecutionObservation] = Field(min_length=1)
    requested_by: str = Field(min_length=1, max_length=120)


class ExecutionScores(BaseModel):
    implementation_shortfall_bps: float
    realized_slippage_bps: float
    explicit_cost_bps: float
    fill_rate: float
    execution_quality: float
    venue_quality: float
    cost_stability: float
    confidence: float


class ExecutionRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: ExecutionState
    scores: ExecutionScores
    risk_flags: List[str]
    approved_by: Optional[str] = None
    version: int = 1


class ExecutionAction(BaseModel):
    action: str = Field(pattern="^(score|submit-review|approve|activate|monitor|suspend|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=120)
    operation_id: str = Field(min_length=1, max_length=160)
    reason: Optional[str] = Field(default=None, max_length=500)
