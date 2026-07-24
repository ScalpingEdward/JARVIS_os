from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class CyberAccessState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    SECURE = "secure"
    IDENTITY_ALERT = "identity-alert"
    PRIVILEGE_ALERT = "privilege-alert"
    CREDENTIAL_ALERT = "credential-alert"
    SEGMENTATION_ALERT = "segmentation-alert"
    DETECTION_GAP = "detection-gap"
    RESPONSE_GAP = "response-gap"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class CyberAccessObservation(BaseModel):
    control_id: str = Field(min_length=2, max_length=128)
    domain: str = Field(min_length=2, max_length=64)
    asset_class: str = Field(min_length=2, max_length=64)
    criticality: float = Field(ge=0.0, le=1.0)
    identity_assurance: float = Field(ge=0.0, le=1.0)
    mfa_coverage: float = Field(ge=0.0, le=1.0)
    least_privilege_coverage: float = Field(ge=0.0, le=1.0)
    privileged_session_monitoring: float = Field(ge=0.0, le=1.0)
    credential_hygiene: float = Field(ge=0.0, le=1.0)
    secret_rotation_coverage: float = Field(ge=0.0, le=1.0)
    network_segmentation: float = Field(ge=0.0, le=1.0)
    endpoint_protection: float = Field(ge=0.0, le=1.0)
    detection_coverage: float = Field(ge=0.0, le=1.0)
    response_readiness: float = Field(ge=0.0, le=1.0)
    logging_coverage: float = Field(ge=0.0, le=1.0)
    patch_compliance: float = Field(ge=0.0, le=1.0)
    open_critical_findings: int = Field(ge=0, le=100000)
    stale_privileged_accounts: int = Field(ge=0, le=100000)
    anomalous_access_events: int = Field(ge=0, le=100000)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)


class CyberAccessGovernanceCreate(BaseModel):
    workspace_id: str = Field(min_length=2, max_length=128)
    source_key: str = Field(min_length=2, max_length=256)
    requested_by: str = Field(min_length=2, max_length=128)
    observations: List[CyberAccessObservation] = Field(min_length=1, max_length=500)
    required_mfa_coverage: float = Field(default=0.95, ge=0.0, le=1.0)
    required_least_privilege_coverage: float = Field(default=0.90, ge=0.0, le=1.0)
    required_detection_coverage: float = Field(default=0.85, ge=0.0, le=1.0)
    max_acceptable_residual_risk: float = Field(default=0.35, ge=0.0, le=1.0)

    @field_validator("observations")
    @classmethod
    def unique_control_ids(cls, observations: List[CyberAccessObservation]) -> List[CyberAccessObservation]:
        ids = [item.control_id for item in observations]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate control_id in observations")
        return observations


class CyberAccessScores(BaseModel):
    identity_security: float
    privilege_security: float
    credential_security: float
    infrastructure_security: float
    detection_response: float
    control_hygiene: float
    aggregate_security: float
    aggregate_residual_risk: float
    confidence: float


class CyberAccessDisposition(BaseModel):
    control_id: str
    domain: str
    security_score: float
    residual_risk: float
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class CyberAccessGovernanceRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: CyberAccessState
    scores: CyberAccessScores
    dispositions: List[CyberAccessDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class CyberAccessAction(BaseModel):
    action: str = Field(min_length=2, max_length=64)
    actor: str = Field(min_length=2, max_length=128)
    operation_id: str = Field(min_length=4, max_length=256)
    reason: Optional[str] = Field(default=None, max_length=1024)
