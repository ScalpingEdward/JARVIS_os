from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CrisisState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    COORDINATION_READY = "coordination-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    COORDINATING = "coordinating"
    CONTAINING = "containing"
    RESOLUTION_READY = "resolution-ready"
    RESOLVING = "resolving"
    STABILIZED = "stabilized"
    RECOVERY_MONITORING = "recovery-monitoring"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class CrisisPortfolio(BaseModel):
    portfolio_id: str = Field(min_length=1)
    capital: float = Field(gt=0)
    drawdown_pct: float = Field(ge=0)
    liquidity_score: float = Field(ge=0, le=100)
    leverage: float = Field(ge=0)
    stress_score: float = Field(ge=0, le=100)
    projected_loss_pct: float = Field(ge=0)
    operational_health: float = Field(ge=0, le=100)
    recovery_capacity: float = Field(ge=0, le=100)


class ResolutionDirective(BaseModel):
    portfolio_id: str = Field(min_length=1)
    action: Literal[
        "freeze-allocation", "reduce-exposure", "reduce-leverage",
        "increase-liquidity", "isolate-portfolio", "orderly-wind-down",
        "transfer-capital", "restore-operations", "return-to-review"
    ]
    magnitude_pct: float = Field(default=0, ge=0, le=100)
    priority: int = Field(default=1, ge=1, le=10)
    rationale: str = Field(min_length=1)


class CrisisPolicy(BaseModel):
    crisis_score_threshold: float = Field(default=65, ge=0, le=100)
    emergency_score_threshold: float = Field(default=82, ge=0, le=100)
    maximum_projected_loss_pct: float = Field(default=12, gt=0)
    minimum_liquidity_score: float = Field(default=45, ge=0, le=100)
    maximum_drawdown_pct: float = Field(default=15, gt=0)
    minimum_operational_health: float = Field(default=55, ge=0, le=100)
    stabilization_cycles_required: int = Field(default=3, ge=1, le=20)
    resolution_cycles_required: int = Field(default=2, ge=1, le=20)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "CrisisPolicy":
        if self.emergency_score_threshold <= self.crisis_score_threshold:
            raise ValueError("emergency_score_threshold must exceed crisis_score_threshold")
        return self


class CrisisCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    incident_id: str = Field(min_length=1)
    portfolios: list[CrisisPortfolio] = Field(min_length=1)
    directives: list[ResolutionDirective] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    policy: CrisisPolicy = Field(default_factory=CrisisPolicy)
    risk_brain_blocked: bool = False

    @model_validator(mode="after")
    def validate_directives(self) -> "CrisisCreate":
        ids = {item.portfolio_id for item in self.portfolios}
        if len(ids) != len(self.portfolios):
            raise ValueError("portfolio_id values must be unique")
        if any(item.portfolio_id not in ids for item in self.directives):
            raise ValueError("directive references unknown portfolio")
        return self


class CrisisAction(BaseModel):
    action: Literal[
        "prepare-evidence", "assess", "prepare-coordination", "request-review",
        "approve", "activate-coordination", "confirm-containment",
        "prepare-resolution", "execute-resolution", "observe",
        "begin-recovery-monitoring", "confirm-resolved", "escalate",
        "suspend", "resume", "revoke", "archive"
    ]
    actor: str = Field(min_length=1)
    approval_token: str | None = None
    operation_receipt: str | None = None
    portfolios: list[CrisisPortfolio] | None = None
    note: str | None = None


class CrisisRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    incident_id: str
    portfolios: list[CrisisPortfolio]
    directives: list[ResolutionDirective]
    evidence_refs: list[str]
    policy: CrisisPolicy
    risk_brain_blocked: bool
    state: CrisisState = CrisisState.DRAFT
    crisis_score: float = 0
    projected_loss_pct: float = 0
    affected_capital: float = 0
    violations: list[str] = Field(default_factory=list)
    stabilization_cycles: int = 0
    resolution_cycles: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: CrisisState
    to_state: CrisisState
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
