from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class PortfolioState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    EVALUATED = "evaluated"
    REBALANCE_PROPOSED = "rebalance-proposed"
    EXECUTIVE_REVIEW_REQUIRED = "executive-review-required"
    APPROVED = "approved"
    ALLOCATED = "allocated"
    MONITORING = "monitoring"
    BALANCED = "balanced"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class AllocationAction(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    HOLD = "hold"
    SUSPEND = "suspend"


class PortfolioSleeve(BaseModel):
    sleeve_id: str = Field(min_length=1, max_length=160)
    mission_id: str = Field(min_length=1, max_length=180)
    strategy_id: str = Field(min_length=1, max_length=180)
    account_id: str = Field(min_length=1, max_length=180)
    broker_id: str = Field(min_length=1, max_length=180)
    current_allocation: float = Field(ge=0)
    maximum_allocation: float = Field(gt=0)
    risk_budget: float = Field(ge=0, le=1)
    current_drawdown: float = Field(default=0, ge=0, le=1)
    performance_score: float = Field(default=0, ge=-1, le=1)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AllocationInstruction(BaseModel):
    instruction_id: str = Field(min_length=1, max_length=160)
    sleeve_id: str = Field(min_length=1, max_length=160)
    action: AllocationAction
    target_allocation: float = Field(ge=0)
    rationale: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(min_length=1)


class StrategicPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    portfolio_name: str = Field(min_length=1, max_length=240)
    strategic_mission_ids: list[str] = Field(min_length=1)
    total_capital: float = Field(gt=0)
    sleeves: list[PortfolioSleeve] = Field(min_length=1)
    instructions: list[AllocationInstruction] = Field(default_factory=list)
    minimum_confidence: float = Field(default=0.8, ge=0, le=1)
    maximum_portfolio_drawdown: float = Field(default=0.1, gt=0, le=1)
    maximum_single_sleeve_weight: float = Field(default=0.5, gt=0, le=1)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    portfolio_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_portfolio(self) -> "StrategicPortfolioCreate":
        sleeve_ids = [item.sleeve_id for item in self.sleeves]
        if len(sleeve_ids) != len(set(sleeve_ids)):
            raise ValueError("sleeve_id values must be unique")
        instruction_ids = [item.instruction_id for item in self.instructions]
        if len(instruction_ids) != len(set(instruction_ids)):
            raise ValueError("instruction_id values must be unique")
        known = set(sleeve_ids)
        if any(item.sleeve_id not in known for item in self.instructions):
            raise ValueError("instructions must reference known sleeves")
        if sum(item.current_allocation for item in self.sleeves) > self.total_capital:
            raise ValueError("current allocations exceed total capital")
        return self


class PortfolioActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|evaluate|propose-rebalance|request-review|approve|allocate|record-cycle|confirm-balanced|escalate|suspend|resume|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    instruction_ids: list[str] = Field(default_factory=list)
    portfolio_drawdown: float | None = Field(default=None, ge=0, le=1)
    cycle_healthy: bool | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: PortfolioState | None = None
    to_state: PortfolioState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class StrategicPortfolio(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    portfolio_name: str
    strategic_mission_ids: list[str]
    total_capital: float
    sleeves: list[PortfolioSleeve]
    instructions: list[AllocationInstruction]
    minimum_confidence: float
    maximum_portfolio_drawdown: float
    maximum_single_sleeve_weight: float
    required_healthy_cycles: int
    portfolio_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: PortfolioState = PortfolioState.DRAFT
    selected_instruction_ids: list[str] = Field(default_factory=list)
    approval_actor: str | None = None
    portfolio_drawdown: float = 0
    consecutive_healthy_cycles: int = 0
    allocation_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
