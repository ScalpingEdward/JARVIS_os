from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class AssuranceState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    TESTING = "testing"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    CERTIFIED = "certified"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class ControlStatus(str, Enum):
    EFFECTIVE = "effective"
    DEFICIENT = "deficient"
    FAILED = "failed"
    NOT_TESTED = "not-tested"


class ControlTest(BaseModel):
    control_id: str = Field(min_length=1, max_length=180)
    control_name: str = Field(min_length=1, max_length=240)
    owner: str = Field(min_length=1, max_length=180)
    status: ControlStatus = ControlStatus.NOT_TESTED
    severity: float = Field(default=0, ge=0, le=1)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CertificationAssertion(BaseModel):
    assertion_id: str = Field(min_length=1, max_length=180)
    title: str = Field(min_length=1, max_length=240)
    conclusion: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(min_length=1)


class AssuranceCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    compliance_record_id: str = Field(min_length=1, max_length=180)
    assurance_name: str = Field(min_length=1, max_length=240)
    controls: list[ControlTest] = Field(min_length=1)
    assertions: list[CertificationAssertion] = Field(min_length=1)
    minimum_assertion_confidence: float = Field(default=0.9, ge=0, le=1)
    maximum_deficient_controls: int = Field(default=0, ge=0)
    maximum_failed_controls: int = Field(default=0, ge=0)
    maximum_control_severity: float = Field(default=0.5, ge=0, le=1)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    assurance_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_records(self) -> "AssuranceCreate":
        control_ids = [item.control_id for item in self.controls]
        assertion_ids = [item.assertion_id for item in self.assertions]
        if len(control_ids) != len(set(control_ids)):
            raise ValueError("control_id values must be unique")
        if len(assertion_ids) != len(set(assertion_ids)):
            raise ValueError("assertion_id values must be unique")
        return self


class AssuranceActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|assess|start-testing|request-review|approve|certify|record-cycle|verify|escalate|suspend|resume|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    cycle_healthy: bool | None = None
    observed_deficient_controls: int | None = Field(default=None, ge=0)
    observed_failed_controls: int | None = Field(default=None, ge=0)
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: AssuranceState | None = None
    to_state: AssuranceState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class AssuranceGovernanceRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    compliance_record_id: str
    assurance_name: str
    controls: list[ControlTest]
    assertions: list[CertificationAssertion]
    minimum_assertion_confidence: float
    maximum_deficient_controls: int
    maximum_failed_controls: int
    maximum_control_severity: float
    required_healthy_cycles: int
    assurance_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: AssuranceState = AssuranceState.DRAFT
    deficient_controls: int = 0
    failed_controls: int = 0
    approval_actor: str | None = None
    consecutive_healthy_cycles: int = 0
    certification_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
