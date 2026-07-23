from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class GovernanceState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    SYNTHESIZED = "synthesized"
    EXECUTIVE_REVIEW_REQUIRED = "executive-review-required"
    APPROVED = "approved"
    DIRECTIVE_ISSUED = "directive-issued"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    ESCALATED = "escalated"
    REVOKED = "revoked"
    REJECTED = "rejected"
    FAILED = "failed"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class GovernanceDomain(str, Enum):
    RISK = "risk"
    RECOVERY = "recovery"
    POLICY = "policy"
    CONFIGURATION = "configuration"
    SECURITY = "security"
    RELIABILITY = "reliability"
    COMPLIANCE = "compliance"
    OPERATIONS = "operations"


class DirectivePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class GovernanceSignal(BaseModel):
    signal_id: str = Field(min_length=1, max_length=160)
    domain: GovernanceDomain
    source_module: str = Field(min_length=1, max_length=180)
    source_record_id: str = Field(min_length=1, max_length=180)
    status: str = Field(min_length=1, max_length=120)
    severity: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=1, max_length=1000)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutiveDirective(BaseModel):
    directive_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    priority: DirectivePriority
    target_domains: list[GovernanceDomain] = Field(min_length=1)
    objective: str = Field(min_length=1, max_length=1000)
    required_actions: list[str] = Field(min_length=1)
    success_criteria: list[str] = Field(min_length=1)
    escalation_conditions: list[str] = Field(default_factory=list)
    expiry_seconds: int = Field(default=86400, ge=60, le=2592000)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GovernanceSynthesisCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    executive_scope: str = Field(min_length=1, max_length=240)
    signals: list[GovernanceSignal] = Field(min_length=1)
    directives: list[ExecutiveDirective] = Field(min_length=1)
    minimum_signal_confidence: float = Field(default=0.75, ge=0, le=1)
    maximum_aggregate_risk: int = Field(default=70, ge=0, le=100)
    monitoring_cycles_required: int = Field(default=3, ge=1, le=100)
    governance_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_payload(self) -> "GovernanceSynthesisCreate":
        signal_ids = [item.signal_id for item in self.signals]
        if len(signal_ids) != len(set(signal_ids)):
            raise ValueError("signal_id values must be unique")
        directive_ids = [item.directive_id for item in self.directives]
        if len(directive_ids) != len(set(directive_ids)):
            raise ValueError("directive_id values must be unique")
        return self


class GovernanceActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|synthesize|request-executive-review|approve|issue-directive|record-monitoring|verify|escalate|revoke|reject|fail|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    directive_ids: list[str] = Field(default_factory=list)
    monitoring_healthy: bool | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: GovernanceState | None = None
    to_state: GovernanceState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class GovernanceSynthesisRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    executive_scope: str
    signals: list[GovernanceSignal]
    directives: list[ExecutiveDirective]
    minimum_signal_confidence: float
    maximum_aggregate_risk: int
    monitoring_cycles_required: int
    governance_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: GovernanceState = GovernanceState.DRAFT
    aggregate_risk: int = 0
    selected_directive_ids: list[str] = Field(default_factory=list)
    approval_actor: str | None = None
    consecutive_healthy_cycles: int = 0
    monitoring_evidence_refs: list[str] = Field(default_factory=list)
    issued_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
