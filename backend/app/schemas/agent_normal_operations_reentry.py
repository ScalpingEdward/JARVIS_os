from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class NormalOperationsReentryState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    NORMAL_OPERATIONS = "normal-operations"
    STABILITY_ALERT = "stability-alert"
    GOVERNANCE_ALERT = "governance-alert"
    OWNERSHIP_ALERT = "ownership-alert"
    RESIDUAL_RISK_ALERT = "residual-risk-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class NormalOperationsReentryObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    stabilization_window_hours: float = Field(ge=0.0)
    service_health_stability: float = Field(ge=0.0, le=1.0)
    latency_stability: float = Field(ge=0.0, le=1.0)
    error_rate_stability: float = Field(ge=0.0, le=1.0)
    state_integrity: float = Field(ge=0.0, le=1.0)
    dependency_health: float = Field(ge=0.0, le=1.0)
    business_kpi_stability: float = Field(ge=0.0, le=1.0)
    error_budget_posture: float = Field(ge=0.0, le=1.0)
    alert_noise_quality: float = Field(ge=0.0, le=1.0)
    operational_owner_readiness: float = Field(ge=0.0, le=1.0)
    runbook_currency: float = Field(ge=0.0, le=1.0)
    handoff_completeness: float = Field(ge=0.0, le=1.0)
    residual_risk_acceptance: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    reopened_incidents: int = Field(default=0, ge=0)
    unresolved_high_findings: int = Field(default=0, ge=0)
    failed_handoffs: int = Field(default=0, ge=0)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class NormalOperationsReentryCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[NormalOperationsReentryObservation] = Field(min_length=1)
    min_stabilization_hours: float = Field(default=24.0, ge=0.0)
    min_stability: float = Field(default=0.90, ge=0.0, le=1.0)
    min_owner_readiness: float = Field(default=0.90, ge=0.0, le=1.0)
    min_handoff_completeness: float = Field(default=0.95, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.25, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_agents(self):
        keys = [o.agent_id for o in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate agent observation")
        return self


class NormalOperationsReentryDisposition(BaseModel):
    agent_id: str
    agent_version: str
    assurance: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class NormalOperationsReentryScores(BaseModel):
    stability_assurance: float = Field(ge=0.0, le=1.0)
    integrity_assurance: float = Field(ge=0.0, le=1.0)
    business_assurance: float = Field(ge=0.0, le=1.0)
    governance_assurance: float = Field(ge=0.0, le=1.0)
    ownership_assurance: float = Field(ge=0.0, le=1.0)
    handoff_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class NormalOperationsReentryRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: NormalOperationsReentryState
    scores: NormalOperationsReentryScores
    dispositions: List[NormalOperationsReentryDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class NormalOperationsReentryAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
