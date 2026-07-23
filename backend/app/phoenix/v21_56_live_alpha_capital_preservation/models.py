from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LiveAlphaState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ANALYZED = "analyzed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    MONITORING = "monitoring"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CAPITAL_WARNING = "capital-warning"
    CAPITAL_REDUCTION = "capital-reduction"
    RECOVERY = "recovery"
    REVALIDATED = "revalidated"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    RETIRED = "retired"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class PerformanceSnapshot(BaseModel):
    observed_at: datetime = Field(default_factory=utcnow)
    realized_alpha_pct: float
    unrealized_alpha_pct: float = 0.0
    rolling_alpha_7d_pct: float
    rolling_alpha_30d_pct: float
    rolling_alpha_90d_pct: float
    drawdown_pct: float = Field(ge=0)
    volatility_pct: float = Field(ge=0)
    sharpe: float
    sortino: float
    profit_factor: float = Field(ge=0)
    recovery_factor: float
    liquidity_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)


class PreservationPolicy(BaseModel):
    minimum_health_score: float = Field(default=65, ge=0, le=100)
    warning_health_score: float = Field(default=50, ge=0, le=100)
    maximum_drawdown_pct: float = Field(default=8, gt=0)
    minimum_sharpe: float = 0.5
    minimum_profit_factor: float = Field(default=1.05, ge=0)
    minimum_liquidity_score: float = Field(default=60, ge=0, le=100)
    alpha_decay_tolerance_pct: float = Field(default=40, ge=0, le=100)
    healthy_cycles_required: int = Field(default=3, ge=1, le=20)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "PreservationPolicy":
        if self.warning_health_score >= self.minimum_health_score:
            raise ValueError("warning_health_score must be below minimum_health_score")
        return self


class LiveAlphaCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    deployed_capital: float = Field(gt=0)
    snapshots: list[PerformanceSnapshot] = Field(min_length=1)
    policy: PreservationPolicy = Field(default_factory=PreservationPolicy)
    evidence_refs: list[str] = Field(default_factory=list)
    risk_brain_blocked: bool = False


class LiveAlphaAction(BaseModel):
    action: Literal[
        "prepare-evidence", "analyze", "request-review", "approve",
        "start-monitoring", "observe", "reduce-capital", "begin-recovery",
        "revalidate", "escalate", "suspend", "resume", "retire",
        "revoke", "archive"
    ]
    actor: str = Field(min_length=1)
    approval_token: str | None = None
    operation_receipt: str | None = None
    snapshot: PerformanceSnapshot | None = None
    note: str | None = None


class LiveAlphaRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    strategy_id: str
    deployed_capital: float
    recommended_capital: float
    state: LiveAlphaState = LiveAlphaState.DRAFT
    snapshots: list[PerformanceSnapshot]
    policy: PreservationPolicy
    evidence_refs: list[str]
    risk_brain_blocked: bool
    health_score: float = 0
    alpha_decay_pct: float = 0
    healthy_cycles: int = 0
    violations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: LiveAlphaState
    to_state: LiveAlphaState
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
