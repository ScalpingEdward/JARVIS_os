from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AccountRiskState(str, Enum):
    blocked = "blocked"
    position_data_required = "position-data-required"
    broker_reconciliation_required = "broker-reconciliation-required"
    daily_loss_breached = "daily-loss-breached"
    drawdown_breached = "drawdown-breached"
    margin_stressed = "margin-stressed"
    exposure_concentrated = "exposure-concentrated"
    correlation_breached = "correlation-breached"
    risk_reduction_required = "risk-reduction-required"
    account_risk_clear = "account-risk-clear"


class AccountRiskObservation(BaseModel):
    position_lifecycle_state: str = Field(default="position-open", min_length=1, max_length=40)
    broker_snapshot_present: bool = True
    broker_balance_reconciled: bool = True
    broker_equity_reconciled: bool = True
    open_positions_reconciled: bool = True
    balance: float = Field(gt=0)
    equity: float = Field(gt=0)
    start_of_day_balance: float = Field(gt=0)
    initial_account_balance: float = Field(gt=0)
    used_margin: float = Field(default=0, ge=0)
    free_margin: float = Field(default=0, ge=0)
    gross_exposure: float = Field(default=0, ge=0)
    net_exposure: float = Field(default=0, ge=0)
    largest_symbol_exposure_pct: float = Field(default=0, ge=0)
    largest_strategy_exposure_pct: float = Field(default=0, ge=0)
    correlated_exposure_pct: float = Field(default=0, ge=0)
    open_risk_pct: float = Field(default=0, ge=0)
    pending_order_risk_pct: float = Field(default=0, ge=0)
    close_or_reduce_requested: bool = False
    human_approval_verified: bool = False
    reduction_acknowledged: bool = True


class AccountRiskPolicy(BaseModel):
    require_position_data: bool = True
    require_broker_reconciliation: bool = True
    maximum_daily_loss_pct: float = Field(default=4.0, gt=0)
    maximum_drawdown_pct: float = Field(default=10.0, gt=0)
    minimum_margin_level_pct: float = Field(default=150.0, gt=0)
    maximum_symbol_exposure_pct: float = Field(default=35.0, gt=0)
    maximum_strategy_exposure_pct: float = Field(default=50.0, gt=0)
    maximum_correlated_exposure_pct: float = Field(default=60.0, gt=0)
    maximum_open_risk_pct: float = Field(default=3.0, gt=0)
    maximum_pending_order_risk_pct: float = Field(default=2.0, gt=0)
    require_human_approval_for_reduction: bool = True


class AccountRiskAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    assessment_id: UUID = Field(default_factory=uuid4)
    account_reference: str = Field(min_length=1, max_length=180)
    broker_reference: str = Field(min_length=1, max_length=180)
    observation: AccountRiskObservation
    risk_brain_clear: bool = True
    policy: AccountRiskPolicy = Field(default_factory=AccountRiskPolicy)


class AccountRiskAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    assessment_id: UUID
    account_reference: str
    broker_reference: str
    state: AccountRiskState
    daily_loss_pct: float
    drawdown_pct: float
    margin_level_pct: float | None
    total_open_risk_pct: float
    reduction_required: bool
    recommended_action: str
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskReductionRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    assessment_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    human_approval_verified: bool = False
    reduction_acknowledged: bool = True
    updated_equity: float = Field(gt=0)
    updated_used_margin: float = Field(default=0, ge=0)
    updated_open_risk_pct: float = Field(default=0, ge=0)


class AccountRiskStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    clear: int
    breached_or_attention: int
    latest_state: AccountRiskState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    record_id: UUID
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
