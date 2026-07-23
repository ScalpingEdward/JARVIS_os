from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RegimeState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    CLASSIFIED = "classified"
    ADAPTATION_READY = "adaptation-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ADAPTING = "adapting"
    MONITORING = "monitoring"
    VALIDATED = "validated"
    REGIME_SHIFT = "regime-shift"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RegimeObservation(BaseModel):
    observed_at: datetime = Field(default_factory=utcnow)
    trend_score: float = Field(ge=0, le=100)
    volatility_score: float = Field(ge=0, le=100)
    liquidity_score: float = Field(ge=0, le=100)
    dispersion_score: float = Field(ge=0, le=100)
    correlation_score: float = Field(ge=0, le=100)
    stress_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)


class AdaptationDirective(BaseModel):
    directive_id: str = Field(default_factory=lambda: str(uuid4()))
    strategy_id: str = Field(min_length=1)
    parameter: Literal[
        "risk-budget", "entry-threshold", "holding-period", "regime-filter",
        "execution-speed", "liquidity-threshold", "position-cap", "research-return"
    ]
    current_value: float | str
    proposed_value: float | str
    rationale: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class RegimePolicy(BaseModel):
    minimum_confidence: float = Field(default=0.7, ge=0, le=1)
    maximum_stress_score: float = Field(default=70, ge=0, le=100)
    minimum_liquidity_score: float = Field(default=55, ge=0, le=100)
    regime_shift_distance: float = Field(default=25, gt=0, le=100)
    validation_cycles_required: int = Field(default=3, ge=1, le=20)
    maximum_directives: int = Field(default=8, ge=1, le=25)


class RegimeCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    strategy_ids: list[str] = Field(min_length=1)
    observations: list[RegimeObservation] = Field(min_length=1)
    directives: list[AdaptationDirective] = Field(default_factory=list)
    policy: RegimePolicy = Field(default_factory=RegimePolicy)
    evidence_refs: list[str] = Field(default_factory=list)
    risk_brain_blocked: bool = False

    @model_validator(mode="after")
    def validate_directives(self) -> "RegimeCreate":
        if len(self.directives) > self.policy.maximum_directives:
            raise ValueError("directive count exceeds policy maximum")
        unknown = {d.strategy_id for d in self.directives} - set(self.strategy_ids)
        if unknown:
            raise ValueError("directive references unknown strategy")
        return self


class RegimeAction(BaseModel):
    action: Literal[
        "prepare-evidence", "classify", "prepare-adaptation", "request-review",
        "approve", "start-adaptation", "observe", "validate", "escalate",
        "suspend", "resume", "revoke", "archive"
    ]
    actor: str = Field(min_length=1)
    approval_token: str | None = None
    operation_receipt: str | None = None
    observation: RegimeObservation | None = None
    note: str | None = None


class RegimeRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    strategy_ids: list[str]
    observations: list[RegimeObservation]
    directives: list[AdaptationDirective]
    policy: RegimePolicy
    evidence_refs: list[str]
    risk_brain_blocked: bool
    state: RegimeState = RegimeState.DRAFT
    regime_label: str = "unclassified"
    regime_confidence: float = 0
    regime_distance: float = 0
    validation_cycles: int = 0
    violations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: RegimeState
    to_state: RegimeState
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
