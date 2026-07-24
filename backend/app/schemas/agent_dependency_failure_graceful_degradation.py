from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class DependencyFailureState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    DEPENDENCY_ALERT = "dependency-alert"
    FAILOVER_ALERT = "failover-alert"
    DEGRADATION_ALERT = "degradation-alert"
    RECOVERY_ALERT = "recovery-alert"
    DATA_INTEGRITY_ALERT = "data-integrity-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class DependencyFailureObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    dependency_id: str = Field(min_length=1, max_length=160)
    dependency_criticality: float = Field(ge=0.0, le=1.0)
    redundancy_coverage: float = Field(ge=0.0, le=1.0)
    failover_readiness: float = Field(ge=0.0, le=1.0)
    fallback_quality: float = Field(ge=0.0, le=1.0)
    graceful_degradation_quality: float = Field(ge=0.0, le=1.0)
    data_integrity_preservation: float = Field(ge=0.0, le=1.0)
    state_consistency: float = Field(ge=0.0, le=1.0)
    recovery_readiness: float = Field(ge=0.0, le=1.0)
    recovery_point_assurance: float = Field(ge=0.0, le=1.0)
    observability_coverage: float = Field(ge=0.0, le=1.0)
    human_override_readiness: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    single_point_failures: int = Field(default=0, ge=0)
    failed_failover_checks: int = Field(default=0, ge=0)
    degradation_violations: int = Field(default=0, ge=0)
    integrity_violations: int = Field(default=0, ge=0)
    failed_recovery_checks: int = Field(default=0, ge=0)


class DependencyFailureCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[DependencyFailureObservation] = Field(min_length=1)
    min_redundancy: float = Field(default=0.85, ge=0.0, le=1.0)
    min_failover: float = Field(default=0.90, ge=0.0, le=1.0)
    min_degradation_quality: float = Field(default=0.85, ge=0.0, le=1.0)
    min_data_integrity: float = Field(default=0.95, ge=0.0, le=1.0)
    min_recovery: float = Field(default=0.90, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.30, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_dependencies(self):
        keys = [(o.agent_id, o.dependency_id) for o in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate agent/dependency observation")
        return self


class DependencyFailureDisposition(BaseModel):
    agent_id: str
    agent_version: str
    dependency_id: str
    assurance: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class DependencyFailureScores(BaseModel):
    redundancy_assurance: float = Field(ge=0.0, le=1.0)
    failover_assurance: float = Field(ge=0.0, le=1.0)
    degradation_assurance: float = Field(ge=0.0, le=1.0)
    integrity_assurance: float = Field(ge=0.0, le=1.0)
    recovery_assurance: float = Field(ge=0.0, le=1.0)
    observability_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class DependencyFailureRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: DependencyFailureState
    scores: DependencyFailureScores
    dispositions: List[DependencyFailureDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class DependencyFailureAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
