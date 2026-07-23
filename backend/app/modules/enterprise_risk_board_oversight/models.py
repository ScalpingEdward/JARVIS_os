from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class EnterpriseRiskState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    AGGREGATED = "aggregated"
    BOARD_PACK_PREPARED = "board-pack-prepared"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    PRESENTED = "presented"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class EnterpriseRiskItem(BaseModel):
    risk_id: str = Field(min_length=1, max_length=180)
    domain: str = Field(min_length=1, max_length=180)
    owner: str = Field(min_length=1, max_length=180)
    level: RiskLevel
    likelihood: float = Field(ge=0, le=1)
    impact: float = Field(ge=0, le=1)
    current_exposure: float = Field(ge=0)
    risk_appetite_limit: float = Field(gt=0)
    control_effectiveness: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BoardDecision(BaseModel):
    decision_id: str = Field(min_length=1, max_length=180)
    title: str = Field(min_length=1, max_length=240)
    recommendation: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(min_length=1)


class EnterpriseRiskCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    assurance_record_id: str = Field(min_length=1, max_length=180)
    register_name: str = Field(min_length=1, max_length=240)
    risks: list[EnterpriseRiskItem] = Field(min_length=1)
    board_decisions: list[BoardDecision] = Field(min_length=1)
    minimum_decision_confidence: float = Field(default=0.9, ge=0, le=1)
    maximum_aggregate_exposure: float = Field(gt=0)
    maximum_critical_risks: int = Field(default=0, ge=0)
    minimum_control_effectiveness: float = Field(default=0.7, ge=0, le=1)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    enterprise_risk_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_records(self) -> "EnterpriseRiskCreate":
        risk_ids = [item.risk_id for item in self.risks]
        decision_ids = [item.decision_id for item in self.board_decisions]
        if len(risk_ids) != len(set(risk_ids)):
            raise ValueError("risk_id values must be unique")
        if len(decision_ids) != len(set(decision_ids)):
            raise ValueError("decision_id values must be unique")
        return self


class EnterpriseRiskActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|aggregate|prepare-board-pack|request-review|approve|present|record-cycle|verify|escalate|suspend|resume|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    cycle_healthy: bool | None = None
    observed_aggregate_exposure: float | None = Field(default=None, ge=0)
    observed_critical_risks: int | None = Field(default=None, ge=0)
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: EnterpriseRiskState | None = None
    to_state: EnterpriseRiskState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class EnterpriseRiskGovernanceRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    assurance_record_id: str
    register_name: str
    risks: list[EnterpriseRiskItem]
    board_decisions: list[BoardDecision]
    minimum_decision_confidence: float
    maximum_aggregate_exposure: float
    maximum_critical_risks: int
    minimum_control_effectiveness: float
    required_healthy_cycles: int
    enterprise_risk_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: EnterpriseRiskState = EnterpriseRiskState.DRAFT
    aggregate_exposure: float = 0
    critical_risks: int = 0
    approval_actor: str | None = None
    consecutive_healthy_cycles: int = 0
    board_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
