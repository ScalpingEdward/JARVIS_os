from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class ReportingState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ATTRIBUTED = "attributed"
    REPORT_GENERATED = "report-generated"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    PUBLISHED = "published"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class AudienceType(str, Enum):
    INTERNAL = "internal"
    EXECUTIVE = "executive"
    INVESTOR = "investor"
    REGULATORY = "regulatory"


class AttributionComponent(BaseModel):
    component_id: str = Field(min_length=1, max_length=180)
    strategy_id: str = Field(min_length=1, max_length=180)
    account_id: str = Field(min_length=1, max_length=180)
    contribution: float
    benchmark_contribution: float = 0
    risk_contribution: float = Field(default=0, ge=0)
    fees: float = Field(default=0, ge=0)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReportSection(BaseModel):
    section_id: str = Field(min_length=1, max_length=180)
    title: str = Field(min_length=1, max_length=240)
    content_summary: str = Field(min_length=1, max_length=4000)
    evidence_refs: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class ReportingCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    financial_close_record_id: str = Field(min_length=1, max_length=180)
    report_name: str = Field(min_length=1, max_length=240)
    reporting_period: str = Field(min_length=1, max_length=120)
    audience: AudienceType
    total_return: float
    benchmark_return: float | None = None
    attribution_components: list[AttributionComponent] = Field(min_length=1)
    sections: list[ReportSection] = Field(min_length=1)
    minimum_section_confidence: float = Field(default=0.8, ge=0, le=1)
    maximum_attribution_variance: float = Field(default=0.01, ge=0, le=1)
    maximum_risk_contribution: float = Field(default=1, ge=0)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    reporting_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_records(self) -> "ReportingCreate":
        component_ids = [item.component_id for item in self.attribution_components]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("component_id values must be unique")
        section_ids = [item.section_id for item in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("section_id values must be unique")
        return self


class ReportingActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|calculate-attribution|generate-report|request-review|approve|publish|record-cycle|verify|escalate|suspend|resume|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    cycle_healthy: bool | None = None
    observed_total_return: float | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: ReportingState | None = None
    to_state: ReportingState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class ReportingGovernanceRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    financial_close_record_id: str
    report_name: str
    reporting_period: str
    audience: AudienceType
    total_return: float
    benchmark_return: float | None = None
    attribution_components: list[AttributionComponent]
    sections: list[ReportSection]
    minimum_section_confidence: float
    maximum_attribution_variance: float
    maximum_risk_contribution: float
    required_healthy_cycles: int
    reporting_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: ReportingState = ReportingState.DRAFT
    attributed_return: float = 0
    attribution_variance: float = 0
    approval_actor: str | None = None
    consecutive_healthy_cycles: int = 0
    publication_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
