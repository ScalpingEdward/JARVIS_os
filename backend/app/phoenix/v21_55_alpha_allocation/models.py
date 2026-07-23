from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class DeploymentState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ANALYZED = "analyzed"
    DEPLOYMENT_READY = "deployment-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    DEPLOYING = "deploying"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class AlphaAllocation(BaseModel):
    allocation_id: str = Field(min_length=1, max_length=180)
    strategy_id: str = Field(min_length=1, max_length=180)
    capital_amount: float = Field(gt=0)
    portfolio_weight: float = Field(gt=0, le=1)
    expected_alpha: float
    expected_volatility: float = Field(ge=0)
    maximum_drawdown: float = Field(ge=0, le=1)
    capacity_limit: float = Field(gt=0)
    liquidity_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    leverage: float = Field(default=1, gt=0)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeploymentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    strategy_factory_record_id: str = Field(min_length=1, max_length=180)
    deployment_name: str = Field(min_length=1, max_length=240)
    total_capital: float = Field(gt=0)
    allocations: list[AlphaAllocation] = Field(min_length=1)
    minimum_confidence: float = Field(default=0.85, ge=0, le=1)
    minimum_liquidity_score: float = Field(default=0.70, ge=0, le=1)
    maximum_portfolio_drawdown: float = Field(default=0.10, ge=0, le=1)
    maximum_total_leverage: float = Field(default=3, gt=0)
    maximum_single_strategy_weight: float = Field(default=0.40, gt=0, le=1)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    deployment_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_allocations(self) -> "DeploymentCreate":
        ids = [item.allocation_id for item in self.allocations]
        strategies = [item.strategy_id for item in self.allocations]
        if len(ids) != len(set(ids)):
            raise ValueError("allocation_id values must be unique")
        if len(strategies) != len(set(strategies)):
            raise ValueError("strategy_id values must be unique")
        if sum(item.capital_amount for item in self.allocations) > self.total_capital + 1e-9:
            raise ValueError("allocated capital exceeds total capital")
        if sum(item.portfolio_weight for item in self.allocations) > 1.000001:
            raise ValueError("portfolio weights exceed 100 percent")
        return self


class DeploymentActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|analyze|prepare-deployment|request-review|approve|deploy|record-cycle|verify|escalate|suspend|resume|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    cycle_healthy: bool | None = None
    observed_drawdown: float | None = Field(default=None, ge=0, le=1)
    observed_total_leverage: float | None = Field(default=None, ge=0)
    observed_liquidity_score: float | None = Field(default=None, ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: DeploymentState | None = None
    to_state: DeploymentState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class CapitalDeploymentRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    strategy_factory_record_id: str
    deployment_name: str
    total_capital: float
    allocations: list[AlphaAllocation]
    minimum_confidence: float
    minimum_liquidity_score: float
    maximum_portfolio_drawdown: float
    maximum_total_leverage: float
    maximum_single_strategy_weight: float
    required_healthy_cycles: int
    deployment_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: DeploymentState = DeploymentState.DRAFT
    allocated_capital: float = 0
    weighted_confidence: float = 0
    weighted_liquidity: float = 0
    projected_drawdown: float = 0
    total_leverage: float = 0
    breached_allocations: int = 0
    consecutive_healthy_cycles: int = 0
    approval_actor: str | None = None
    deployment_evidence: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
