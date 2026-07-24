from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentProductionCertificationState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    CERTIFIED = "certified"
    ENVIRONMENT_ALERT = "environment-alert"
    SIGNOFF_ALERT = "signoff-alert"
    RELEASE_GATE_ALERT = "release-gate-alert"
    CHANGE_WINDOW_ALERT = "change-window-alert"
    RECOVERY_ALERT = "recovery-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AgentProductionCertificationObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    target_environment: str = Field(min_length=1, max_length=120)
    environment_parity_score: float = Field(ge=0.0, le=1.0)
    artifact_integrity_score: float = Field(ge=0.0, le=1.0)
    configuration_integrity_score: float = Field(ge=0.0, le=1.0)
    dependency_lock_score: float = Field(ge=0.0, le=1.0)
    security_signoff_coverage: float = Field(ge=0.0, le=1.0)
    risk_signoff_coverage: float = Field(ge=0.0, le=1.0)
    operations_signoff_coverage: float = Field(ge=0.0, le=1.0)
    change_window_readiness: float = Field(ge=0.0, le=1.0)
    release_gate_coverage: float = Field(ge=0.0, le=1.0)
    observability_baseline_score: float = Field(ge=0.0, le=1.0)
    rollback_recovery_readiness: float = Field(ge=0.0, le=1.0)
    break_glass_readiness: float = Field(ge=0.0, le=1.0)
    runbook_readiness: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    unresolved_blocking_findings: int = Field(default=0, ge=0)
    missing_required_signoffs: int = Field(default=0, ge=0)
    environment_drift_events: int = Field(default=0, ge=0)
    failed_release_gate_checks: int = Field(default=0, ge=0)
    rollback_recovery_failures: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentProductionCertificationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[AgentProductionCertificationObservation] = Field(min_length=1)
    min_environment_parity: float = Field(default=0.90, ge=0.0, le=1.0)
    min_signoff_coverage: float = Field(default=0.95, ge=0.0, le=1.0)
    min_release_gate_coverage: float = Field(default=0.95, ge=0.0, le=1.0)
    min_recovery_readiness: float = Field(default=0.90, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.30, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_agent_environment_pairs(self):
        pairs = [(o.agent_id, o.target_environment) for o in self.observations]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate agent/environment observation")
        return self


class AgentProductionCertificationDisposition(BaseModel):
    agent_id: str
    agent_version: str
    target_environment: str
    certification_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentProductionCertificationScores(BaseModel):
    environment_assurance: float = Field(ge=0.0, le=1.0)
    artifact_configuration_assurance: float = Field(ge=0.0, le=1.0)
    signoff_assurance: float = Field(ge=0.0, le=1.0)
    release_gate_assurance: float = Field(ge=0.0, le=1.0)
    observability_assurance: float = Field(ge=0.0, le=1.0)
    recovery_assurance: float = Field(ge=0.0, le=1.0)
    operational_readiness: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentProductionCertificationRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentProductionCertificationState
    scores: AgentProductionCertificationScores
    dispositions: List[AgentProductionCertificationDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentProductionCertificationAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
