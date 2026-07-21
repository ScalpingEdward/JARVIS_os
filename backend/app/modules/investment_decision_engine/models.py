from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class InvestmentDecisionState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    ANALYSIS_PENDING = "analysis-pending"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    DECISION_READY = "decision-ready"
    APPROVED = "approved"
    ISSUED_TO_EXECUTION_PLANNING = "issued-to-execution-planning"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"


class InvestmentOption(BaseModel):
    option_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=240)
    required_capital: float = Field(ge=0)
    expected_value: float = Field(ge=0)
    probability_of_success: float = Field(ge=0, le=1)
    time_to_value_months: float = Field(gt=0)
    strategic_alignment: float = Field(ge=0, le=100)
    reversibility: float = Field(ge=0, le=100)
    residual_risk_score: float = Field(ge=0, le=100)
    dependencies_ready: bool = True
    evidence_refs: list[str] = Field(default_factory=list)


class InvestmentDecisionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_risk_register_id: str = Field(min_length=1, max_length=160)
    source_key: str = Field(min_length=1, max_length=200)
    available_capital: float = Field(gt=0)
    minimum_expected_roi: float = Field(default=0.1, ge=-1, le=20)
    maximum_residual_risk: float = Field(default=60, ge=0, le=100)
    strategic_constraints: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    options: list[InvestmentOption] = Field(min_length=1)
    risk_brain_hard_block: bool = False

    @model_validator(mode="after")
    def unique_options(self) -> "InvestmentDecisionCreate":
        ids = [item.option_id for item in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError("option_id values must be unique")
        return self


class InvestmentScore(BaseModel):
    option_id: str
    expected_monetary_value: float
    expected_roi: float
    risk_adjusted_value: float
    capital_efficiency: float
    strategic_score: float
    composite_score: float
    recommendation: Literal["invest", "conditional", "defer", "reject"]
    reasons: list[str] = Field(default_factory=list)


class InvestmentDecisionRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_risk_register_id: str
    source_key: str
    state: InvestmentDecisionState = InvestmentDecisionState.ANALYSIS_PENDING
    available_capital: float
    minimum_expected_roi: float
    maximum_residual_risk: float
    strategic_constraints: list[str]
    evidence_refs: list[str]
    options: list[InvestmentOption]
    scores: list[InvestmentScore] = Field(default_factory=list)
    selected_option_ids: list[str] = Field(default_factory=list)
    committed_capital: float = 0
    portfolio_expected_value: float = 0
    portfolio_expected_roi: float = 0
    confidence_score: float = 0
    escalation_reasons: list[str] = Field(default_factory=list)
    approval_token: str | None = None
    downstream_receipt: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InvestmentDecisionExecute(BaseModel):
    action: Literal["analyze", "approve", "reject", "issue", "archive"]
    actor_id: str = Field(min_length=1, max_length=160)
    approval_token: str | None = None
    downstream_receipt: str | None = None
    note: str | None = Field(default=None, max_length=2000)


class InvestmentDecisionAuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor_id: str
    from_state: InvestmentDecisionState
    to_state: InvestmentDecisionState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
