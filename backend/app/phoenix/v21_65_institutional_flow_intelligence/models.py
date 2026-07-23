from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FlowState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    SCORED = "scored"
    POLICY_READY = "policy-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    STABLE = "stable"
    FLOW_SHIFT = "flow-shift"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class InstitutionalFlowSignal(BaseModel):
    signal_id: str = Field(min_length=1)
    asset: str = Field(min_length=1)
    venue: str = Field(min_length=1)
    source_type: Literal[
        "etf-flow", "fund-flow", "block-trade", "dark-pool", "prime-broker",
        "dealer-inventory", "custody-flow", "futures-positioning", "cot",
        "repo", "money-market", "bond-flow", "fx-fixing", "cross-border",
    ]
    direction: Literal["inflow", "outflow", "accumulation", "distribution", "neutral"]
    notional_usd: float = Field(ge=0)
    participation_pct: float = Field(default=0, ge=0, le=100)
    persistence_score: float = Field(default=50, ge=0, le=100)
    concentration_score: float = Field(default=50, ge=0, le=100)
    confidence: float = Field(default=50, ge=0, le=100)
    freshness: float = Field(default=100, ge=0, le=100)
    provenance_score: float = Field(default=50, ge=0, le=100)


class FlowPolicy(BaseModel):
    shift_threshold: float = Field(default=25, gt=0, le=100)
    escalation_threshold: float = Field(default=75, gt=0, le=100)
    minimum_confidence: float = Field(default=55, ge=0, le=100)
    minimum_data_quality: float = Field(default=50, ge=0, le=100)
    maximum_concentration: float = Field(default=85, ge=0, le=100)
    stable_cycles_required: int = Field(default=2, ge=1, le=20)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "FlowPolicy":
        if self.escalation_threshold <= self.shift_threshold:
            raise ValueError("escalation_threshold must exceed shift_threshold")
        return self


class FlowCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    universe: str = Field(min_length=1)
    signals: list[InstitutionalFlowSignal] = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    policy: FlowPolicy = Field(default_factory=FlowPolicy)
    risk_brain_blocked: bool = False

    @model_validator(mode="after")
    def validate_signals(self) -> "FlowCreate":
        ids = {item.signal_id for item in self.signals}
        if len(ids) != len(self.signals):
            raise ValueError("signal_id values must be unique")
        return self


class FlowAction(BaseModel):
    action: Literal[
        "prepare-evidence", "score", "prepare-policy", "request-review", "approve",
        "activate", "observe", "suspend", "resume", "escalate", "revoke", "archive",
    ]
    actor: str = Field(min_length=1)
    approval_token: str | None = None
    operation_receipt: str | None = None
    signals: list[InstitutionalFlowSignal] | None = None
    note: str | None = None


class FlowRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    universe: str
    signals: list[InstitutionalFlowSignal]
    evidence_refs: list[str]
    policy: FlowPolicy
    risk_brain_blocked: bool
    state: FlowState = FlowState.DRAFT
    net_flow_score: float = 0
    institutional_pressure_score: float = 0
    concentration_risk: float = 0
    data_quality_score: float = 0
    confidence_score: float = 0
    flow_dispersion: float = 0
    violations: list[str] = Field(default_factory=list)
    stable_cycles: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: FlowState
    to_state: FlowState
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
