from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class StrategyRuntimeState(str, Enum):
    BLOCKED = "blocked"
    PORTFOLIO_REQUIRED = "portfolio-required"
    STRATEGY_INVALID = "strategy-invalid"
    SIGNAL_STALE = "signal-stale"
    REGIME_MISMATCH = "regime-mismatch"
    CONFLICT_DETECTED = "conflict-detected"
    CAPACITY_REJECTED = "capacity-rejected"
    RISK_REJECTED = "risk-rejected"
    APPROVAL_REQUIRED = "approval-required"
    SCHEDULED = "scheduled"
    DISPATCH_PENDING = "dispatch-pending"
    EXECUTION_PENDING = "execution-pending"
    RECONCILIATION_REQUIRED = "reconciliation-required"
    RUNTIME_ACTIVE = "runtime-active"
    PAUSED = "paused"
    FAILED = "failed"


class StrategyCandidate(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=30)
    side: str
    signal_age_seconds: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    expected_rr: float = Field(gt=0)
    requested_risk_amount: float = Field(gt=0)
    regime: str = Field(min_length=1, max_length=50)
    priority: int = Field(default=100, ge=0)
    enabled: bool = True


class StrategyRuntimeAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=150)
    actor_id: str = Field(min_length=1, max_length=100)
    portfolio_ready: bool = False
    candidates: list[StrategyCandidate] = Field(default_factory=list)
    current_regime: str = Field(min_length=1, max_length=50)
    max_signal_age_seconds: int = Field(default=120, ge=1)
    minimum_confidence: float = Field(default=0.6, ge=0, le=1)
    minimum_expected_rr: float = Field(default=1.5, gt=0)
    max_concurrent_strategies: int = Field(default=3, ge=1)
    active_strategy_count: int = Field(default=0, ge=0)
    available_risk_budget: float = Field(gt=0)
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    human_approved: bool = False
    dispatch_requested: bool = False
    dispatch_acknowledged: bool = False
    execution_started: bool = False
    runtime_reconciled: bool = False
    pause_requested: bool = False
    terminal_error: str | None = None
    risk_brain_blocked: bool = False


class StrategyRuntimeExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    human_approved: bool | None = None
    dispatch_requested: bool | None = None
    dispatch_acknowledged: bool | None = None
    execution_started: bool | None = None
    runtime_reconciled: bool | None = None
    pause_requested: bool | None = None
    terminal_error: str | None = None


class StrategyRuntimeAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    state: StrategyRuntimeState
    reasons: list[str] = Field(default_factory=list)
    selected_strategy_ids: list[str] = Field(default_factory=list)
    payload: StrategyRuntimeAssessmentCreate
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StrategyRuntimeStatus(BaseModel):
    workspace_id: str
    latest_state: StrategyRuntimeState | None
    count: int


class AuditRecord(BaseModel):
    workspace_id: str
    action: str
    actor_id: str
    record_id: UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
