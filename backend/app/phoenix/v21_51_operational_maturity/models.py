from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class MaturityState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    IMPROVEMENT_PLAN_READY = "improvement-plan-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    IMPLEMENTING = "implementing"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class InitiativeStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    FAILED = "failed"


class MaturityDomain(BaseModel):
    domain_id: str = Field(min_length=1, max_length=180)
    domain: str = Field(min_length=1, max_length=180)
    owner: str = Field(min_length=1, max_length=180)
    current_score: float = Field(ge=0, le=5)
    target_score: float = Field(ge=0, le=5)
    minimum_acceptable_score: float = Field(ge=0, le=5)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImprovementInitiative(BaseModel):
    initiative_id: str = Field(min_length=1, max_length=180)
    domain_id: str = Field(min_length=1, max_length=180)
    title: str = Field(min_length=1, max_length=240)
    owner: str = Field(min_length=1, max_length=180)
    priority: int = Field(ge=1, le=100)
    expected_score_gain: float = Field(ge=0, le=5)
    confidence: float = Field(ge=0, le=1)
    status: InitiativeStatus = InitiativeStatus.PROPOSED
    reversible: bool = True
    evidence_refs: list[str] = Field(min_length=1)


class MaturityCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    resilience_record_id: str = Field(min_length=1, max_length=180)
    program_name: str = Field(min_length=1, max_length=240)
    domains: list[MaturityDomain] = Field(min_length=1)
    initiatives: list[ImprovementInitiative] = Field(min_length=1)
    minimum_initiative_confidence: float = Field(default=0.85, ge=0, le=1)
    minimum_average_maturity: float = Field(default=3, ge=0, le=5)
    maximum_below_minimum_domains: int = Field(default=0, ge=0)
    maximum_failed_initiatives: int = Field(default=0, ge=0)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    maturity_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_records(self) -> "MaturityCreate":
        domain_ids = [item.domain_id for item in self.domains]
        initiative_ids = [item.initiative_id for item in self.initiatives]
        if len(domain_ids) != len(set(domain_ids)):
            raise ValueError("domain_id values must be unique")
        if len(initiative_ids) != len(set(initiative_ids)):
            raise ValueError("initiative_id values must be unique")
        known_domains = set(domain_ids)
        if any(item.domain_id not in known_domains for item in self.initiatives):
            raise ValueError("initiative domain_id must reference a known domain")
        return self


class MaturityActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|assess|prepare-improvement-plan|request-review|approve|implement|record-cycle|verify|escalate|suspend|resume|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    cycle_healthy: bool | None = None
    observed_average_maturity: float | None = Field(default=None, ge=0, le=5)
    observed_below_minimum_domains: int | None = Field(default=None, ge=0)
    observed_failed_initiatives: int | None = Field(default=None, ge=0)
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: MaturityState | None = None
    to_state: MaturityState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class MaturityGovernanceRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    resilience_record_id: str
    program_name: str
    domains: list[MaturityDomain]
    initiatives: list[ImprovementInitiative]
    minimum_initiative_confidence: float
    minimum_average_maturity: float
    maximum_below_minimum_domains: int
    maximum_failed_initiatives: int
    required_healthy_cycles: int
    maturity_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: MaturityState = MaturityState.DRAFT
    average_maturity: float = 0
    below_minimum_domains: int = 0
    failed_initiatives: int = 0
    approval_actor: str | None = None
    consecutive_healthy_cycles: int = 0
    implementation_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
