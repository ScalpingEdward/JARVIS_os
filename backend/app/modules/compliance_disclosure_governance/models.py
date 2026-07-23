from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class ComplianceState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    DISCLOSURE_PREPARED = "disclosure-prepared"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    FILED = "filed"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class ObligationStatus(str, Enum):
    OPEN = "open"
    SATISFIED = "satisfied"
    BREACHED = "breached"
    WAIVED = "waived"


class RegulatoryObligation(BaseModel):
    obligation_id: str = Field(min_length=1, max_length=180)
    jurisdiction: str = Field(min_length=1, max_length=120)
    authority: str = Field(min_length=1, max_length=180)
    requirement: str = Field(min_length=1, max_length=1000)
    due_at: datetime | None = None
    status: ObligationStatus = ObligationStatus.OPEN
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DisclosureItem(BaseModel):
    disclosure_id: str = Field(min_length=1, max_length=180)
    title: str = Field(min_length=1, max_length=240)
    content_summary: str = Field(min_length=1, max_length=4000)
    jurisdiction: str = Field(min_length=1, max_length=120)
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(min_length=1)


class ComplianceCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    reporting_record_id: str = Field(min_length=1, max_length=180)
    compliance_name: str = Field(min_length=1, max_length=240)
    obligations: list[RegulatoryObligation] = Field(min_length=1)
    disclosures: list[DisclosureItem] = Field(min_length=1)
    minimum_disclosure_confidence: float = Field(default=0.85, ge=0, le=1)
    maximum_open_obligations: int = Field(default=0, ge=0)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    compliance_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_records(self) -> "ComplianceCreate":
        obligation_ids = [item.obligation_id for item in self.obligations]
        disclosure_ids = [item.disclosure_id for item in self.disclosures]
        if len(obligation_ids) != len(set(obligation_ids)):
            raise ValueError("obligation_id values must be unique")
        if len(disclosure_ids) != len(set(disclosure_ids)):
            raise ValueError("disclosure_id values must be unique")
        return self


class ComplianceActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|assess|prepare-disclosure|request-review|approve|file|record-cycle|verify|escalate|suspend|resume|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    cycle_healthy: bool | None = None
    observed_open_obligations: int | None = Field(default=None, ge=0)
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: ComplianceState | None = None
    to_state: ComplianceState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class ComplianceGovernanceRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    reporting_record_id: str
    compliance_name: str
    obligations: list[RegulatoryObligation]
    disclosures: list[DisclosureItem]
    minimum_disclosure_confidence: float
    maximum_open_obligations: int
    required_healthy_cycles: int
    compliance_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: ComplianceState = ComplianceState.DRAFT
    open_obligations: int = 0
    approval_actor: str | None = None
    consecutive_healthy_cycles: int = 0
    filing_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
