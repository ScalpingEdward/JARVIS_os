from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class AssuranceState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    DRAFT = "draft"
    EVALUATED = "evaluated"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    ATTESTED = "attested"
    REMEDIATION_QUEUED = "remediation-queued"
    REMEDIATED = "remediated"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FAILED = "failed"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class AssuranceBand(str, Enum):
    NON_COMPLIANT = "non-compliant"
    WEAK = "weak"
    CONDITIONAL = "conditional"
    COMPLIANT = "compliant"
    ATTESTED = "attested"


class PolicyControl(BaseModel):
    control_id: str = Field(min_length=1, max_length=120)
    policy_id: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=500)
    weight: float = Field(gt=0, le=1)
    required: bool = True
    expected_value: str = Field(min_length=1, max_length=300)
    observed_value: str = Field(min_length=1, max_length=300)
    evidence_ref: str = Field(min_length=1, max_length=300)
    compliant: bool


class RemediationControl(BaseModel):
    remediation_id: str = Field(min_length=1, max_length=120)
    control_id: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=500)
    owner: str = Field(min_length=1, max_length=180)
    expected_risk_reduction: float = Field(ge=0, le=1)
    requires_restart: bool = False


class AssuranceAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    trust_assessment_id: str = Field(min_length=1, max_length=180)
    policy_version: str = Field(min_length=1, max_length=160)
    configuration_version: str = Field(min_length=1, max_length=160)
    runtime_ids: list[str] = Field(min_length=1)
    controls: list[PolicyControl] = Field(min_length=1)
    remediations: list[RemediationControl] = Field(default_factory=list)
    trust_evidence_refs: list[str] = Field(min_length=1)
    runtime_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_integrity(self) -> "AssuranceAssessmentCreate":
        control_ids = [item.control_id for item in self.controls]
        if len(control_ids) != len(set(control_ids)):
            raise ValueError("control_id values must be unique")
        remediation_ids = [item.remediation_id for item in self.remediations]
        if len(remediation_ids) != len(set(remediation_ids)):
            raise ValueError("remediation_id values must be unique")
        if len(self.runtime_ids) != len(set(self.runtime_ids)):
            raise ValueError("runtime_ids must be unique")
        total_weight = sum(item.weight for item in self.controls)
        if abs(total_weight - 1.0) > 1e-6:
            raise ValueError("control weights must total exactly 1.0")
        known = set(control_ids)
        if any(item.control_id not in known for item in self.remediations):
            raise ValueError("every remediation must reference a known control")
        return self


class AssuranceActionRequest(BaseModel):
    action: str = Field(pattern="^(evaluate|request-review|approve|attest|queue-remediation|complete-remediation|verify|reject|fail|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    attestation_digest: str | None = Field(default=None, max_length=256)
    applied_remediation_ids: list[str] = Field(default_factory=list)
    verification_evidence_refs: list[str] = Field(default_factory=list)
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


class AssuranceAssessment(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    trust_assessment_id: str
    policy_version: str
    configuration_version: str
    runtime_ids: list[str]
    controls: list[PolicyControl]
    remediations: list[RemediationControl]
    trust_evidence_refs: list[str]
    runtime_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: AssuranceState = AssuranceState.DRAFT
    assurance_score: float = 0.0
    failed_control_count: int = 0
    required_failure_count: int = 0
    band: AssuranceBand = AssuranceBand.NON_COMPLIANT
    approval_actor: str | None = None
    attestation_digest: str | None = None
    applied_remediation_ids: list[str] = Field(default_factory=list)
    verification_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
