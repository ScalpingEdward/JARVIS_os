from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentContinuousResilienceState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    STABLE = "stable"
    BASELINE_ALERT = "baseline-alert"
    REGRESSION_ALERT = "regression-alert"
    DRIFT_ALERT = "drift-alert"
    RECURRENCE_ALERT = "recurrence-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AgentContinuousResilienceObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    baseline_id: str = Field(min_length=1, max_length=160)
    availability_score: float = Field(ge=0.0, le=1.0)
    latency_stability_score: float = Field(ge=0.0, le=1.0)
    error_rate_stability_score: float = Field(ge=0.0, le=1.0)
    recovery_time_score: float = Field(ge=0.0, le=1.0)
    failover_stability_score: float = Field(ge=0.0, le=1.0)
    dependency_stability_score: float = Field(ge=0.0, le=1.0)
    observability_stability_score: float = Field(ge=0.0, le=1.0)
    control_effectiveness_score: float = Field(ge=0.0, le=1.0)
    recurrence_prevention_score: float = Field(ge=0.0, le=1.0)
    regression_coverage_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    baseline_breaches: int = Field(default=0, ge=0)
    failed_regression_checks: int = Field(default=0, ge=0)
    resilience_drift_events: int = Field(default=0, ge=0)
    repeated_incident_count: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentContinuousResilienceCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[AgentContinuousResilienceObservation] = Field(min_length=1)
    min_baseline_stability: float = Field(default=0.90, ge=0.0, le=1.0)
    min_regression_coverage: float = Field(default=0.90, ge=0.0, le=1.0)
    min_recurrence_prevention: float = Field(default=0.90, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.30, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_agent_baseline_pairs(self):
        pairs = [(o.agent_id, o.baseline_id) for o in self.observations]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate agent/baseline observation")
        return self


class AgentContinuousResilienceDisposition(BaseModel):
    agent_id: str
    agent_version: str
    baseline_id: str
    resilience_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentContinuousResilienceScores(BaseModel):
    service_stability: float = Field(ge=0.0, le=1.0)
    recovery_assurance: float = Field(ge=0.0, le=1.0)
    dependency_assurance: float = Field(ge=0.0, le=1.0)
    observability_assurance: float = Field(ge=0.0, le=1.0)
    control_assurance: float = Field(ge=0.0, le=1.0)
    recurrence_assurance: float = Field(ge=0.0, le=1.0)
    regression_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentContinuousResilienceRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentContinuousResilienceState
    scores: AgentContinuousResilienceScores
    dispositions: List[AgentContinuousResilienceDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentContinuousResilienceAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
