from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AlternativeDataState(str, Enum):
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
    SIGNAL_SHIFT = "signal-shift"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AlternativeSignal(BaseModel):
    source_id: str = Field(min_length=1)
    source_type: Literal[
        "satellite", "web-traffic", "app-usage", "card-spend", "shipping",
        "supply-chain", "job-postings", "search-trends", "social", "mobility",
        "weather", "energy", "inventory", "pricing", "custom"
    ]
    entity: str = Field(min_length=1)
    value: float
    normalized_score: float = Field(ge=-100, le=100)
    confidence: float = Field(ge=0, le=100)
    freshness_minutes: int = Field(ge=0)
    coverage_score: float = Field(ge=0, le=100)
    provenance_ref: str = Field(min_length=1)


class AlternativeDataPolicy(BaseModel):
    minimum_confidence: float = Field(default=60, ge=0, le=100)
    minimum_coverage: float = Field(default=55, ge=0, le=100)
    maximum_freshness_minutes: int = Field(default=1440, ge=1)
    signal_shift_threshold: float = Field(default=35, ge=0, le=100)
    escalation_threshold: float = Field(default=70, ge=0, le=100)
    stable_cycles_required: int = Field(default=3, ge=1, le=20)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "AlternativeDataPolicy":
        if self.escalation_threshold <= self.signal_shift_threshold:
            raise ValueError("escalation_threshold must exceed signal_shift_threshold")
        return self


class AlternativeDataCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    signals: list[AlternativeSignal] = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    policy: AlternativeDataPolicy = Field(default_factory=AlternativeDataPolicy)
    risk_brain_blocked: bool = False

    @model_validator(mode="after")
    def validate_signals(self) -> "AlternativeDataCreate":
        ids = {item.source_id for item in self.signals}
        if len(ids) != len(self.signals):
            raise ValueError("source_id values must be unique")
        return self


class AlternativeDataAction(BaseModel):
    action: Literal[
        "prepare-evidence", "score", "prepare-policy", "request-review", "approve",
        "activate", "observe", "confirm-stable", "escalate", "suspend", "resume",
        "revoke", "archive"
    ]
    actor: str = Field(min_length=1)
    approval_token: str | None = None
    operation_receipt: str | None = None
    signals: list[AlternativeSignal] | None = None
    note: str | None = None


class AlternativeDataRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    subject_id: str
    signals: list[AlternativeSignal]
    evidence_refs: list[str]
    policy: AlternativeDataPolicy
    risk_brain_blocked: bool
    state: AlternativeDataState = AlternativeDataState.DRAFT
    composite_score: float = 0
    confidence_score: float = 0
    data_quality_score: float = 0
    signal_dispersion: float = 0
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
    from_state: AlternativeDataState
    to_state: AlternativeDataState
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
