from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class RecoveryCertificationState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    CERTIFIED = "certified"
    RECOVERY_ALERT = "recovery-alert"
    INTEGRITY_ALERT = "integrity-alert"
    OBSERVABILITY_ALERT = "observability-alert"
    BUSINESS_ALERT = "business-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RecoveryCertificationObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    recovery_id: str = Field(min_length=1, max_length=160)
    service_health_score: float = Field(ge=0.0, le=1.0)
    state_integrity_score: float = Field(ge=0.0, le=1.0)
    data_integrity_score: float = Field(ge=0.0, le=1.0)
    dependency_health_score: float = Field(ge=0.0, le=1.0)
    observability_score: float = Field(ge=0.0, le=1.0)
    error_budget_readiness: float = Field(ge=0.0, le=1.0)
    capacity_headroom: float = Field(ge=0.0, le=1.0)
    business_validation_score: float = Field(ge=0.0, le=1.0)
    rollback_readiness: float = Field(ge=0.0, le=1.0)
    human_signoff_coverage: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    unresolved_recovery_findings: int = Field(default=0, ge=0)
    integrity_failures: int = Field(default=0, ge=0)
    observability_gaps: int = Field(default=0, ge=0)
    business_validation_failures: int = Field(default=0, ge=0)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class RecoveryCertificationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[RecoveryCertificationObservation] = Field(min_length=1)
    min_service_health: float = Field(default=0.95, ge=0.0, le=1.0)
    min_integrity: float = Field(default=0.95, ge=0.0, le=1.0)
    min_observability: float = Field(default=0.90, ge=0.0, le=1.0)
    min_business_validation: float = Field(default=0.90, ge=0.0, le=1.0)
    min_human_signoff: float = Field(default=1.0, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.25, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_recoveries(self):
        keys = [(o.agent_id, o.recovery_id) for o in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate agent/recovery observation")
        return self


class RecoveryCertificationDisposition(BaseModel):
    agent_id: str
    agent_version: str
    recovery_id: str
    certification_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class RecoveryCertificationScores(BaseModel):
    health_assurance: float = Field(ge=0.0, le=1.0)
    integrity_assurance: float = Field(ge=0.0, le=1.0)
    dependency_assurance: float = Field(ge=0.0, le=1.0)
    observability_assurance: float = Field(ge=0.0, le=1.0)
    capacity_assurance: float = Field(ge=0.0, le=1.0)
    business_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class RecoveryCertificationRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: RecoveryCertificationState
    scores: RecoveryCertificationScores
    dispositions: List[RecoveryCertificationDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class RecoveryCertificationAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
