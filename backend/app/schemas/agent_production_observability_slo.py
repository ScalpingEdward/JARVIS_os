from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentProductionObservabilityState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    HEALTHY = "healthy"
    SLO_ALERT = "slo-alert"
    ERROR_BUDGET_ALERT = "error-budget-alert"
    TELEMETRY_ALERT = "telemetry-alert"
    INCIDENT_ALERT = "incident-alert"
    DRIFT_ALERT = "drift-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AgentProductionObservabilityObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    production_environment: str = Field(min_length=1, max_length=120)
    availability_slo_attainment: float = Field(ge=0.0, le=1.0)
    latency_slo_attainment: float = Field(ge=0.0, le=1.0)
    error_rate_slo_attainment: float = Field(ge=0.0, le=1.0)
    telemetry_coverage: float = Field(ge=0.0, le=1.0)
    trace_coverage: float = Field(ge=0.0, le=1.0)
    log_quality: float = Field(ge=0.0, le=1.0)
    metric_quality: float = Field(ge=0.0, le=1.0)
    alert_precision: float = Field(ge=0.0, le=1.0)
    incident_detection_readiness: float = Field(ge=0.0, le=1.0)
    human_oncall_readiness: float = Field(ge=0.0, le=1.0)
    runbook_coverage: float = Field(ge=0.0, le=1.0)
    error_budget_remaining: float = Field(ge=0.0, le=1.0)
    behavioral_drift_score: float = Field(ge=0.0, le=1.0)
    decision_drift_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    slo_breaches: int = Field(default=0, ge=0)
    telemetry_gaps: int = Field(default=0, ge=0)
    critical_incidents: int = Field(default=0, ge=0)
    unresolved_incidents: int = Field(default=0, ge=0)
    false_negative_alerts: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentProductionObservabilityCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[AgentProductionObservabilityObservation] = Field(min_length=1)
    min_slo_attainment: float = Field(default=0.95, ge=0.0, le=1.0)
    min_telemetry_coverage: float = Field(default=0.90, ge=0.0, le=1.0)
    min_error_budget_remaining: float = Field(default=0.25, ge=0.0, le=1.0)
    max_drift_score: float = Field(default=0.25, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.30, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_agent_environment_pairs(self):
        pairs = [(o.agent_id, o.production_environment) for o in self.observations]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate agent/environment observation")
        return self


class AgentProductionObservabilityDisposition(BaseModel):
    agent_id: str
    agent_version: str
    production_environment: str
    production_health_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentProductionObservabilityScores(BaseModel):
    slo_assurance: float = Field(ge=0.0, le=1.0)
    telemetry_assurance: float = Field(ge=0.0, le=1.0)
    alerting_assurance: float = Field(ge=0.0, le=1.0)
    incident_readiness: float = Field(ge=0.0, le=1.0)
    error_budget_assurance: float = Field(ge=0.0, le=1.0)
    drift_assurance: float = Field(ge=0.0, le=1.0)
    operational_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentProductionObservabilityRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentProductionObservabilityState
    scores: AgentProductionObservabilityScores
    dispositions: List[AgentProductionObservabilityDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentProductionObservabilityAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
