from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class IncidentSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class IncidentState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    OPEN = "open"
    CONTAINMENT_REQUIRED = "containment-required"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    CONTAINED = "contained"
    RECOVERY_IN_PROGRESS = "recovery-in-progress"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    FAILED = "failed"
    ARCHIVED = "archived"


class RecoveryStep(BaseModel):
    step_id: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=200)
    requires_human_approval: bool = True
    completed: bool = False


class IncidentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=240)
    severity: IncidentSeverity
    reconciliation_record_id: str = Field(min_length=1)
    runtime_record_id: str = Field(min_length=1)
    command_record_ids: list[str] = Field(default_factory=list)
    drift_codes: list[str] = Field(default_factory=list)
    recovery_steps: list[RecoveryStep] = Field(default_factory=list)
    upstream_evidence_verified: bool = False
    risk_brain_blocked: bool = False

    @model_validator(mode="after")
    def validate_unique_steps(self):
        ids = [step.step_id for step in self.recovery_steps]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate recovery step")
        return self


class IncidentAction(BaseModel):
    action: Literal[
        "request-containment",
        "approve",
        "contain",
        "start-recovery",
        "complete-step",
        "monitor",
        "resolve",
        "fail",
        "archive",
    ]
    actor_id: str = Field(min_length=1, max_length=100)
    approval_token: str | None = None
    receipt_id: str | None = None
    step_id: str | None = None
    reason: str | None = Field(default=None, max_length=500)


class IncidentRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    title: str
    severity: IncidentSeverity
    reconciliation_record_id: str
    runtime_record_id: str
    command_record_ids: list[str]
    drift_codes: list[str]
    recovery_steps: list[RecoveryStep]
    state: IncidentState
    upstream_evidence_verified: bool
    risk_brain_blocked: bool
    approval_token_hash: str | None = None
    last_receipt_id: str | None = None
    contained_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor_id: str
    state: IncidentState
    reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
