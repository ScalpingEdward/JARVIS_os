from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RecoveryState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    DIAGNOSED = "diagnosed"
    PLAN_READY = "plan-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    RECOVERING = "recovering"
    REVALIDATING = "revalidating"
    REVALIDATED = "revalidated"
    CONDITIONAL_RETURN = "conditional-return"
    RESTORED = "restored"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    RETIRED = "retired"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RecoveryObservation(BaseModel):
    observed_at: datetime = Field(default_factory=utcnow)
    alpha_pct: float
    drawdown_pct: float = Field(ge=0)
    sharpe: float
    profit_factor: float = Field(ge=0)
    win_rate_pct: float = Field(ge=0, le=100)
    execution_quality_score: float = Field(ge=0, le=100)
    regime_fit_score: float = Field(ge=0, le=100)
    liquidity_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)


class RecoveryIntervention(BaseModel):
    intervention_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=1)
    category: Literal[
        "risk-reduction",
        "parameter-adjustment",
        "regime-filter",
        "execution-control",
        "liquidity-control",
        "research-return",
    ]
    rationale: str = Field(min_length=1)
    reversible: bool = True
    expected_health_improvement: float = Field(ge=0, le=100)
    evidence_refs: list[str] = Field(default_factory=list)


class RevalidationGate(BaseModel):
    gate_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=1)
    score: float = Field(ge=0, le=100)
    minimum_score: float = Field(ge=0, le=100)
    evidence_refs: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.score >= self.minimum_score


class RecoveryPolicy(BaseModel):
    maximum_recovery_drawdown_pct: float = Field(default=5, gt=0)
    minimum_revalidation_pass_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_regime_fit_score: float = Field(default=65, ge=0, le=100)
    minimum_execution_quality_score: float = Field(default=70, ge=0, le=100)
    minimum_liquidity_score: float = Field(default=60, ge=0, le=100)
    minimum_confidence: float = Field(default=0.7, ge=0, le=1)
    required_healthy_cycles: int = Field(default=3, ge=1, le=20)
    conditional_return_capital_pct: float = Field(default=25, gt=0, le=100)


class RecoveryCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    originating_live_alpha_record_id: str = Field(min_length=1)
    baseline_capital: float = Field(gt=0)
    observations: list[RecoveryObservation] = Field(min_length=1)
    interventions: list[RecoveryIntervention] = Field(min_length=1)
    gates: list[RevalidationGate] = Field(min_length=1)
    policy: RecoveryPolicy = Field(default_factory=RecoveryPolicy)
    evidence_refs: list[str] = Field(default_factory=list)
    risk_brain_blocked: bool = False

    @model_validator(mode="after")
    def validate_unique_items(self) -> "RecoveryCreate":
        if len({item.intervention_id for item in self.interventions}) != len(self.interventions):
            raise ValueError("intervention_id values must be unique")
        if len({gate.gate_id for gate in self.gates}) != len(self.gates):
            raise ValueError("gate_id values must be unique")
        return self


class RecoveryAction(BaseModel):
    action: Literal[
        "prepare-evidence",
        "diagnose",
        "prepare-plan",
        "request-review",
        "approve",
        "start-recovery",
        "observe",
        "start-revalidation",
        "complete-revalidation",
        "authorize-conditional-return",
        "restore",
        "escalate",
        "suspend",
        "resume",
        "retire",
        "revoke",
        "archive",
    ]
    actor: str = Field(min_length=1)
    approval_token: str | None = None
    operation_receipt: str | None = None
    observation: RecoveryObservation | None = None
    gate_updates: list[RevalidationGate] | None = None
    note: str | None = None


class RecoveryRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    strategy_id: str
    originating_live_alpha_record_id: str
    baseline_capital: float
    recommended_return_capital: float = 0
    state: RecoveryState = RecoveryState.DRAFT
    observations: list[RecoveryObservation]
    interventions: list[RecoveryIntervention]
    gates: list[RevalidationGate]
    policy: RecoveryPolicy
    evidence_refs: list[str]
    risk_brain_blocked: bool
    recovery_health_score: float = 0
    revalidation_pass_rate: float = 0
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
    from_state: RecoveryState
    to_state: RecoveryState
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
