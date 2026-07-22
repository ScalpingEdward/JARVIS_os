from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class RiskState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    ASSESSMENT_PENDING = "assessment-pending"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    RISK_APPROVED = "risk-approved"
    APPROVED = "approved"
    ISSUED_TO_EXPOSURE_MANAGER = "issued-to-exposure-manager"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"
    ARCHIVED = "archived"


class AccountRiskSnapshot(BaseModel):
    balance: float = Field(gt=0)
    equity: float = Field(gt=0)
    daily_start_equity: float = Field(gt=0)
    initial_account_size: float = Field(gt=0)
    open_risk_amount: float = Field(default=0, ge=0)
    realized_daily_pnl: float = 0
    consecutive_losses: int = Field(default=0, ge=0)
    volatility_score: float = Field(default=50, ge=0, le=100)
    correlation_exposure_score: float = Field(default=0, ge=0, le=100)


class RiskPolicy(BaseModel):
    base_risk_percent: float = Field(default=0.5, gt=0, le=10)
    minimum_risk_percent: float = Field(default=0.1, gt=0, le=10)
    maximum_risk_percent: float = Field(default=1.0, gt=0, le=10)
    maximum_daily_loss_percent: float = Field(default=4.0, gt=0, le=100)
    maximum_total_drawdown_percent: float = Field(default=10.0, gt=0, le=100)
    maximum_aggregate_open_risk_percent: float = Field(default=2.0, gt=0, le=100)
    losing_streak_soft_limit: int = Field(default=2, ge=0)
    losing_streak_hard_limit: int = Field(default=4, ge=1)
    high_volatility_threshold: float = Field(default=75, ge=0, le=100)
    high_correlation_threshold: float = Field(default=70, ge=0, le=100)

    @model_validator(mode="after")
    def validate_bounds(self) -> "RiskPolicy":
        if not self.minimum_risk_percent <= self.base_risk_percent <= self.maximum_risk_percent:
            raise ValueError("risk percentages must satisfy minimum <= base <= maximum")
        if self.losing_streak_soft_limit > self.losing_streak_hard_limit:
            raise ValueError("soft losing-streak limit cannot exceed hard limit")
        return self


class DynamicRiskCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    position_management_record_id: str = Field(min_length=1, max_length=180)
    v21_16_approved: bool
    v21_16_evidence: dict[str, Any] = Field(default_factory=dict)
    risk_brain_hard_block: bool = False
    symbol: str = Field(min_length=1, max_length=40)
    direction: Literal["long", "short"]
    setup_grade: Literal["A+", "A", "B", "C", "rejected"]
    setup_confidence_score: float = Field(ge=0, le=100)
    entry_price: float
    stop_price: float
    value_per_price_unit: float = Field(gt=0)
    account: AccountRiskSnapshot
    policy: RiskPolicy = Field(default_factory=RiskPolicy)
    active_news_risk: bool = False

    @model_validator(mode="after")
    def validate_geometry(self) -> "DynamicRiskCreate":
        if self.entry_price == self.stop_price:
            raise ValueError("entry and stop cannot be equal")
        if self.direction == "long" and self.stop_price >= self.entry_price:
            raise ValueError("long stop must be below entry")
        if self.direction == "short" and self.stop_price <= self.entry_price:
            raise ValueError("short stop must be above entry")
        return self


class RiskAssessment(BaseModel):
    recommended_risk_percent: float
    recommended_risk_amount: float
    recommended_position_units: float
    stop_distance: float
    daily_loss_percent: float
    total_drawdown_percent: float
    aggregate_open_risk_percent: float
    risk_multiplier: float
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)


class DynamicRiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    position_management_record_id: str
    symbol: str
    direction: str
    state: RiskState
    assessment: RiskAssessment
    approval_token: str | None = None
    downstream_receipt: str | None = None
    notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskCommand(str, Enum):
    APPROVE = "approve"
    ISSUE = "issue"
    REJECT = "reject"
    INVALIDATE = "invalidate"
    ARCHIVE = "archive"


class RiskAction(BaseModel):
    command: RiskCommand
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = None
    downstream_receipt: str | None = None
    reason: str | None = Field(default=None, max_length=4000)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    record_id: str
    action: str
    actor: str
    from_state: str | None = None
    to_state: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
