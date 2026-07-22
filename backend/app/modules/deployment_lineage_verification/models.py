from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VerificationState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    DRAFT = "draft"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    DRIFT_DETECTED = "drift-detected"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    REMEDIATION_QUEUED = "remediation-queued"
    RESOLVED = "resolved"
    FAILED = "failed"
    ARCHIVED = "archived"


class CheckSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DeploymentCheck(BaseModel):
    check_id: str = Field(min_length=1)
    component: str = Field(min_length=1)
    expected_value: Any
    observed_value: Any
    severity: CheckSeverity = CheckSeverity.WARNING
    passed: bool | None = None
    evidence_ref: str | None = None


class DeploymentVerificationCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    rollout_id: str = Field(min_length=1)
    runtime_id: str = Field(min_length=1)
    previous_config_version: str = Field(min_length=1)
    deployed_config_version: str = Field(min_length=1)
    artifact_digest: str = Field(min_length=8)
    rollout_evidence_ref: str | None = None
    runtime_evidence_ref: str | None = None
    risk_brain_blocked: bool = False
    checks: list[DeploymentCheck] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_checks(self) -> "DeploymentVerificationCreate":
        ids = [item.check_id for item in self.checks]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate deployment check_id")
        return self


class VerificationAction(BaseModel):
    action: str = Field(pattern="^(verify|approve|queue-remediation|resolve|fail|archive)$")
    actor_id: str = Field(min_length=1)
    approval_token: str | None = None
    receipt_id: str | None = None
    completed_check_ids: list[str] = Field(default_factory=list)
    note: str | None = None


class DeploymentVerificationRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    rollout_id: str
    runtime_id: str
    previous_config_version: str
    deployed_config_version: str
    artifact_digest: str
    rollout_evidence_ref: str | None = None
    runtime_evidence_ref: str | None = None
    risk_brain_blocked: bool = False
    checks: list[DeploymentCheck]
    state: VerificationState
    lineage: list[str]
    drift_count: int = 0
    critical_drift_count: int = 0
    approval_token: str | None = None
    action_receipts: set[str] = Field(default_factory=set)
    remediation_completed_check_ids: set[str] = Field(default_factory=set)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AuditEntry(BaseModel):
    audit_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    record_id: str
    action: str
    actor_id: str
    from_state: VerificationState
    to_state: VerificationState
    note: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
