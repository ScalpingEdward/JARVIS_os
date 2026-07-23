from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class MultiBrokerState(str, Enum):
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
    LATENCY_ALERT = "latency-alert"
    EXECUTION_DEGRADATION = "execution-degradation"
    COUNTERPARTY_ALERT = "counterparty-alert"
    CAPACITY_ALERT = "capacity-alert"
    ROUTING_REVIEW = "routing-review"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class BrokerObservation(BaseModel):
    broker_id: str = Field(min_length=1, max_length=120)
    venue_type: str = Field(min_length=1, max_length=80)
    asset_class: str = Field(min_length=1, max_length=80)
    quoted_spread_bps: float = Field(ge=0)
    realized_spread_bps: float = Field(ge=0)
    median_latency_ms: float = Field(ge=0)
    p95_latency_ms: float = Field(ge=0)
    fill_rate: float = Field(ge=0, le=1)
    rejection_rate: float = Field(ge=0, le=1)
    slippage_bps: float
    partial_fill_rate: float = Field(ge=0, le=1)
    uptime: float = Field(ge=0, le=1)
    liquidity_score: float = Field(ge=0, le=1)
    counterparty_score: float = Field(ge=0, le=1)
    regulatory_score: float = Field(ge=0, le=1)
    capacity_utilization: float = Field(ge=0, le=1)
    current_routing_weight: float = Field(ge=0, le=1)
    confidence: float = Field(default=1, ge=0, le=1)
    freshness: float = Field(default=1, ge=0, le=1)
    provenance: List[str] = Field(default_factory=list)


class MultiBrokerCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=160)
    observations: List[BrokerObservation] = Field(min_length=1)
    max_broker_weight: float = Field(default=0.50, gt=0, le=1)
    max_latency_ms: float = Field(default=250, gt=0)
    min_fill_rate: float = Field(default=0.95, ge=0, le=1)
    max_rejection_rate: float = Field(default=0.03, ge=0, le=1)
    min_counterparty_score: float = Field(default=0.70, ge=0, le=1)
    requested_by: str = Field(min_length=1, max_length=120)


class BrokerRecommendation(BaseModel):
    broker_id: str
    execution_quality_score: float
    reliability_score: float
    counterparty_resilience_score: float
    capacity_score: float
    recommended_routing_weight: float
    routing_signal: str


class MultiBrokerScores(BaseModel):
    aggregate_execution_quality: float
    routing_resilience: float
    liquidity_quality: float
    counterparty_resilience: float
    regulatory_resilience: float
    capacity_headroom: float
    concentration_quality: float
    confidence: float


class MultiBrokerRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: MultiBrokerState
    scores: MultiBrokerScores
    recommendations: List[BrokerRecommendation]
    risk_flags: List[str]
    approved_by: Optional[str] = None
    version: int = 1


class MultiBrokerAction(BaseModel):
    action: str = Field(pattern="^(score|submit-review|approve|activate|monitor|suspend|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=120)
    operation_id: str = Field(min_length=1, max_length=160)
    reason: Optional[str] = Field(default=None, max_length=500)
