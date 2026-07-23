from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class InfrastructureHealthState(str, Enum):
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
    DATA_DEGRADATION = "data-degradation"
    CONNECTIVITY_ALERT = "connectivity-alert"
    CAPACITY_ALERT = "capacity-alert"
    FAILOVER_REQUIRED = "failover-required"
    INCIDENT = "incident"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class InfrastructureObservation(BaseModel):
    venue_id: str = Field(min_length=1, max_length=120)
    region: str = Field(min_length=1, max_length=80)
    gateway_latency_ms: float = Field(ge=0)
    market_data_latency_ms: float = Field(ge=0)
    order_ack_latency_ms: float = Field(ge=0)
    packet_loss_rate: float = Field(ge=0, le=1)
    disconnect_rate: float = Field(ge=0, le=1)
    stale_quote_rate: float = Field(ge=0, le=1)
    uptime_rate: float = Field(ge=0, le=1)
    cpu_utilization: float = Field(ge=0, le=1)
    memory_utilization: float = Field(ge=0, le=1)
    queue_utilization: float = Field(ge=0, le=1)
    error_rate: float = Field(ge=0, le=1)
    failover_readiness: float = Field(ge=0, le=1)
    time_sync_drift_ms: float = Field(ge=0)
    confidence: float = Field(default=1, ge=0, le=1)
    freshness: float = Field(default=1, ge=0, le=1)
    provenance: List[str] = Field(default_factory=list)


class InfrastructureHealthCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=160)
    observations: List[InfrastructureObservation] = Field(min_length=1)
    max_gateway_latency_ms: float = Field(default=120, gt=0)
    max_packet_loss_rate: float = Field(default=0.01, ge=0, le=1)
    min_uptime_rate: float = Field(default=0.995, ge=0, le=1)
    max_queue_utilization: float = Field(default=0.85, ge=0, le=1)
    requested_by: str = Field(min_length=1, max_length=120)


class InfrastructureVenueAssessment(BaseModel):
    venue_id: str
    connectivity_score: float
    data_integrity_score: float
    latency_score: float
    capacity_score: float
    failover_score: float
    health_score: float
    operational_signal: str


class InfrastructureHealthScores(BaseModel):
    aggregate_health: float
    connectivity_resilience: float
    market_data_integrity: float
    execution_path_health: float
    capacity_headroom: float
    failover_readiness: float
    clock_integrity: float
    confidence: float


class InfrastructureHealthRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: InfrastructureHealthState
    scores: InfrastructureHealthScores
    assessments: List[InfrastructureVenueAssessment]
    risk_flags: List[str]
    approved_by: Optional[str] = None
    version: int = 1


class InfrastructureHealthAction(BaseModel):
    action: str = Field(pattern="^(score|submit-review|approve|activate|monitor|suspend|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=120)
    operation_id: str = Field(min_length=1, max_length=160)
    reason: Optional[str] = Field(default=None, max_length=500)
