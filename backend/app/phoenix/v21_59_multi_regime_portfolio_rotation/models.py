from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RotationState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ANALYZED = "analyzed"
    ROTATION_READY = "rotation-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ROTATING = "rotating"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    REBALANCE_REQUIRED = "rebalance-required"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RegimeSleeve(BaseModel):
    sleeve_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    target_regime: Literal["stressed", "volatile-trend", "stable-trend", "range-bound", "transitional"]
    current_weight_pct: float = Field(ge=0, le=100)
    proposed_weight_pct: float = Field(ge=0, le=100)
    expected_alpha_pct: float
    drawdown_pct: float = Field(ge=0)
    liquidity_score: float = Field(ge=0, le=100)
    regime_fit_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    correlation_bucket: str = Field(min_length=1)
    capacity_limit: float = Field(gt=0)
    proposed_capital: float = Field(ge=0)


class RotationPolicy(BaseModel):
    minimum_regime_fit: float = Field(default=65, ge=0, le=100)
    minimum_liquidity_score: float = Field(default=60, ge=0, le=100)
    minimum_confidence: float = Field(default=0.65, ge=0, le=1)
    maximum_single_sleeve_weight_pct: float = Field(default=35, gt=0, le=100)
    maximum_bucket_weight_pct: float = Field(default=50, gt=0, le=100)
    maximum_projected_drawdown_pct: float = Field(default=8, gt=0)
    maximum_turnover_pct: float = Field(default=40, gt=0, le=100)
    verification_cycles_required: int = Field(default=3, ge=1, le=20)


class RotationCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    portfolio_id: str = Field(min_length=1)
    active_regime: str = Field(min_length=1)
    total_capital: float = Field(gt=0)
    sleeves: list[RegimeSleeve] = Field(min_length=1)
    policy: RotationPolicy = Field(default_factory=RotationPolicy)
    evidence_refs: list[str] = Field(default_factory=list)
    risk_brain_blocked: bool = False

    @model_validator(mode="after")
    def validate_weights_and_capital(self) -> "RotationCreate":
        proposed_weight = sum(s.proposed_weight_pct for s in self.sleeves)
        proposed_capital = sum(s.proposed_capital for s in self.sleeves)
        if abs(proposed_weight - 100) > 0.01:
            raise ValueError("proposed sleeve weights must total 100 percent")
        if proposed_capital > self.total_capital + 0.01:
            raise ValueError("proposed capital exceeds total capital")
        return self


class RotationAction(BaseModel):
    action: Literal[
        "prepare-evidence", "analyze", "prepare-rotation", "request-review",
        "approve", "start-rotation", "observe", "require-rebalance",
        "escalate", "suspend", "resume", "revoke", "archive"
    ]
    actor: str = Field(min_length=1)
    approval_token: str | None = None
    operation_receipt: str | None = None
    sleeves: list[RegimeSleeve] | None = None
    note: str | None = None


class RotationRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    portfolio_id: str
    active_regime: str
    total_capital: float
    sleeves: list[RegimeSleeve]
    policy: RotationPolicy
    evidence_refs: list[str]
    risk_brain_blocked: bool
    state: RotationState = RotationState.DRAFT
    projected_drawdown_pct: float = 0
    turnover_pct: float = 0
    weighted_regime_fit: float = 0
    weighted_liquidity: float = 0
    weighted_confidence: float = 0
    verification_cycles: int = 0
    violations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: RotationState
    to_state: RotationState
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
