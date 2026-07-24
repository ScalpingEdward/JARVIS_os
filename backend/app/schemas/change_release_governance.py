from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class ChangeReleaseState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    RELEASE_READY = "release-ready"
    TEST_GAP = "test-gap"
    ROLLBACK_GAP = "rollback-gap"
    SEGREGATION_ALERT = "segregation-alert"
    SECURITY_ALERT = "security-alert"
    OBSERVABILITY_GAP = "observability-gap"
    CHANGE_RISK_ALERT = "change-risk-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class ChangeObservation(BaseModel):
    change_id: str
    component: str
    change_type: str = "standard"
    criticality: float = Field(ge=0.0, le=1.0)
    test_coverage: float = Field(ge=0.0, le=1.0)
    regression_coverage: float = Field(ge=0.0, le=1.0)
    rollback_readiness: float = Field(ge=0.0, le=1.0)
    peer_review_coverage: float = Field(ge=0.0, le=1.0)
    segregation_of_duties: float = Field(ge=0.0, le=1.0)
    security_review_coverage: float = Field(ge=0.0, le=1.0)
    dependency_impact_known: float = Field(ge=0.0, le=1.0)
    observability_readiness: float = Field(ge=0.0, le=1.0)
    canary_readiness: float = Field(ge=0.0, le=1.0)
    deployment_rehearsal: float = Field(ge=0.0, le=1.0)
    open_blocking_findings: int = Field(ge=0)
    recent_failed_releases: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)


class ChangeReleaseGovernanceCreate(BaseModel):
    workspace_id: str
    source_key: str
    requested_by: str
    required_test_coverage: float = Field(default=0.80, ge=0.0, le=1.0)
    required_rollback_readiness: float = Field(default=0.80, ge=0.0, le=1.0)
    max_acceptable_risk: float = Field(default=0.45, ge=0.0, le=1.0)
    observations: List[ChangeObservation] = Field(min_length=1)


class ChangeDisposition(BaseModel):
    change_id: str
    component: str
    readiness_score: float
    residual_risk: float
    lifecycle_signal: str
    required_actions: List[str]


class ChangeReleaseScores(BaseModel):
    test_assurance: float
    rollback_resilience: float
    review_integrity: float
    security_assurance: float
    dependency_readiness: float
    observability_readiness: float
    deployment_readiness: float
    aggregate_release_assurance: float
    aggregate_residual_risk: float
    confidence: float


class ChangeReleaseGovernanceRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: ChangeReleaseState
    scores: ChangeReleaseScores
    dispositions: List[ChangeDisposition]
    risk_flags: List[str]
    approved_by: str | None = None
    version: int = 1


class ChangeReleaseAction(BaseModel):
    workspace_id: str
    action: str
    actor: str
    operation_id: str
    reason: str | None = None
