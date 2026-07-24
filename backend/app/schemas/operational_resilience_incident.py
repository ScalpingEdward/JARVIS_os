from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class OperationalResilienceState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    RESILIENT = "resilient"
    RECOVERY_RISK = "recovery-risk"
    DEPENDENCY_ALERT = "dependency-alert"
    CAPACITY_ALERT = "capacity-alert"
    INCIDENT_ALERT = "incident-alert"
    CONTINUITY_GAP = "continuity-gap"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class ResilienceObservation(BaseModel):
    service_id: str = Field(min_length=1, max_length=120)
    criticality: float = Field(ge=0.0, le=1.0)
    availability_score: float = Field(ge=0.0, le=1.0)
    recovery_readiness: float = Field(ge=0.0, le=1.0)
    continuity_readiness: float = Field(ge=0.0, le=1.0)
    dependency_resilience: float = Field(ge=0.0, le=1.0)
    capacity_headroom: float = Field(ge=0.0, le=1.0)
    cyber_resilience: float = Field(ge=0.0, le=1.0)
    runbook_coverage: float = Field(ge=0.0, le=1.0)
    recovery_test_coverage: float = Field(ge=0.0, le=1.0)
    incident_count_30d: int = Field(ge=0)
    open_sev1_incidents: int = Field(ge=0)
    rto_breach_risk: float = Field(ge=0.0, le=1.0)
    rpo_breach_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    freshness: float = Field(ge=0.0, le=1.0, default=1.0)


class OperationalResilienceCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    requested_by: str = Field(min_length=1, max_length=120)
    observations: List[ResilienceObservation] = Field(min_length=1)
    minimum_recovery_readiness: float = Field(ge=0.0, le=1.0, default=0.75)
    minimum_continuity_readiness: float = Field(ge=0.0, le=1.0, default=0.75)
    maximum_acceptable_residual_risk: float = Field(ge=0.0, le=1.0, default=0.45)


class OperationalResilienceScores(BaseModel):
    service_availability: float
    recovery_strength: float
    continuity_strength: float
    dependency_resilience: float
    capacity_resilience: float
    cyber_resilience: float
    aggregate_resilience: float
    aggregate_residual_risk: float
    confidence: float


class ServiceResilienceDisposition(BaseModel):
    service_id: str
    resilience_score: float
    residual_risk: float
    lifecycle_signal: str
    required_actions: List[str]


class OperationalResilienceRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: OperationalResilienceState
    scores: OperationalResilienceScores
    dispositions: List[ServiceResilienceDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class OperationalResilienceAction(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=80)
    actor: str = Field(min_length=1, max_length=120)
    operation_id: str = Field(min_length=1, max_length=180)
    reason: Optional[str] = Field(default=None, max_length=500)
