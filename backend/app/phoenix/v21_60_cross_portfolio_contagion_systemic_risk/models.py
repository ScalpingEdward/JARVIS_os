from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SystemicRiskState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    MAPPED = "mapped"
    ANALYZED = "analyzed"
    CONTAINMENT_READY = "containment-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    CONTAINING = "containing"
    MONITORING = "monitoring"
    STABLE = "stable"
    CONTAGION_WARNING = "contagion-warning"
    SYSTEMIC_ALERT = "systemic-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class PortfolioNode(BaseModel):
    portfolio_id: str = Field(min_length=1)
    gross_exposure: float = Field(ge=0)
    net_exposure: float
    drawdown_pct: float = Field(ge=0)
    liquidity_score: float = Field(ge=0, le=100)
    leverage: float = Field(ge=0)
    stress_score: float = Field(ge=0, le=100)
    capital_share_pct: float = Field(ge=0, le=100)


class ContagionLink(BaseModel):
    source_portfolio_id: str = Field(min_length=1)
    target_portfolio_id: str = Field(min_length=1)
    correlation: float = Field(ge=-1, le=1)
    shared_factor_exposure_pct: float = Field(ge=0, le=100)
    shared_liquidity_dependency_pct: float = Field(ge=0, le=100)
    transmission_probability: float = Field(ge=0, le=1)
    loss_amplification: float = Field(ge=0)

    @model_validator(mode="after")
    def different_nodes(self) -> "ContagionLink":
        if self.source_portfolio_id == self.target_portfolio_id:
            raise ValueError("contagion link requires different portfolios")
        return self


class SystemicRiskPolicy(BaseModel):
    maximum_systemic_risk_score: float = Field(default=65, ge=0, le=100)
    warning_systemic_risk_score: float = Field(default=50, ge=0, le=100)
    maximum_portfolio_stress_score: float = Field(default=75, ge=0, le=100)
    minimum_liquidity_score: float = Field(default=55, ge=0, le=100)
    maximum_link_transmission_probability: float = Field(default=0.65, ge=0, le=1)
    maximum_correlation_concentration: float = Field(default=0.8, ge=0, le=1)
    maximum_projected_loss_pct: float = Field(default=12, gt=0)
    stable_cycles_required: int = Field(default=3, ge=1, le=20)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "SystemicRiskPolicy":
        if self.warning_systemic_risk_score >= self.maximum_systemic_risk_score:
            raise ValueError("warning threshold must be below maximum threshold")
        return self


class ContainmentDirective(BaseModel):
    portfolio_id: str = Field(min_length=1)
    action: Literal[
        "reduce-exposure", "reduce-leverage", "increase-liquidity-buffer",
        "isolate-factor", "freeze-new-allocation", "suspend-rotation",
        "return-to-review"
    ]
    reduction_pct: float = Field(default=0, ge=0, le=100)
    rationale: str = Field(min_length=1)


class SystemicRiskCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    portfolio_group_id: str = Field(min_length=1)
    nodes: list[PortfolioNode] = Field(min_length=2)
    links: list[ContagionLink] = Field(min_length=1)
    directives: list[ContainmentDirective] = Field(default_factory=list)
    policy: SystemicRiskPolicy = Field(default_factory=SystemicRiskPolicy)
    evidence_refs: list[str] = Field(default_factory=list)
    risk_brain_blocked: bool = False


class SystemicRiskAction(BaseModel):
    action: Literal[
        "prepare-evidence", "map-network", "analyze", "prepare-containment",
        "request-review", "approve", "start-containment", "observe",
        "escalate", "suspend", "resume", "revoke", "archive"
    ]
    actor: str = Field(min_length=1)
    approval_token: str | None = None
    operation_receipt: str | None = None
    nodes: list[PortfolioNode] | None = None
    links: list[ContagionLink] | None = None
    note: str | None = None


class SystemicRiskRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    portfolio_group_id: str
    state: SystemicRiskState
    nodes: list[PortfolioNode]
    links: list[ContagionLink]
    directives: list[ContainmentDirective]
    policy: SystemicRiskPolicy
    evidence_refs: list[str]
    risk_brain_blocked: bool
    systemic_risk_score: float = 0
    projected_loss_pct: float = 0
    concentration_score: float = 0
    contagion_paths: int = 0
    stable_cycles: int = 0
    violations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: SystemicRiskState
    to_state: SystemicRiskState
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
