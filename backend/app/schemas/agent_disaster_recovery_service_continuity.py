from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class DisasterRecoveryState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    RTO_ALERT = "rto-alert"
    RPO_ALERT = "rpo-alert"
    BACKUP_ALERT = "backup-alert"
    RECOVERY_ALERT = "recovery-alert"
    CONTINUITY_ALERT = "continuity-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class DisasterRecoveryObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    service_id: str = Field(min_length=1, max_length=160)
    rto_readiness: float = Field(ge=0.0, le=1.0)
    rpo_readiness: float = Field(ge=0.0, le=1.0)
    backup_integrity: float = Field(ge=0.0, le=1.0)
    restore_readiness: float = Field(ge=0.0, le=1.0)
    regional_redundancy: float = Field(ge=0.0, le=1.0)
    dependency_recovery_readiness: float = Field(ge=0.0, le=1.0)
    state_reconstruction_readiness: float = Field(ge=0.0, le=1.0)
    communication_readiness: float = Field(ge=0.0, le=1.0)
    runbook_coverage: float = Field(ge=0.0, le=1.0)
    recovery_test_coverage: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    failed_restore_tests: int = Field(default=0, ge=0)
    failed_recovery_tests: int = Field(default=0, ge=0)
    stale_backup_events: int = Field(default=0, ge=0)
    continuity_gaps: int = Field(default=0, ge=0)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class DisasterRecoveryCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[DisasterRecoveryObservation] = Field(min_length=1)
    min_rto_readiness: float = Field(default=0.90, ge=0.0, le=1.0)
    min_rpo_readiness: float = Field(default=0.90, ge=0.0, le=1.0)
    min_backup_integrity: float = Field(default=0.95, ge=0.0, le=1.0)
    min_recovery_readiness: float = Field(default=0.90, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.30, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_services(self):
        pairs = [(o.agent_id, o.service_id) for o in self.observations]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate agent/service observation")
        return self


class DisasterRecoveryDisposition(BaseModel):
    agent_id: str
    agent_version: str
    service_id: str
    assurance: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class DisasterRecoveryScores(BaseModel):
    rto_assurance: float = Field(ge=0.0, le=1.0)
    rpo_assurance: float = Field(ge=0.0, le=1.0)
    backup_restore_assurance: float = Field(ge=0.0, le=1.0)
    continuity_assurance: float = Field(ge=0.0, le=1.0)
    dependency_recovery_assurance: float = Field(ge=0.0, le=1.0)
    operational_readiness: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class DisasterRecoveryRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: DisasterRecoveryState
    scores: DisasterRecoveryScores
    dispositions: List[DisasterRecoveryDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class DisasterRecoveryAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
