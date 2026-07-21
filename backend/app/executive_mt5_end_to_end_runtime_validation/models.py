from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PipelineState(StrEnum):
    BLOCKED = "blocked"
    RUNTIME_REQUIRED = "runtime-required"
    DEPENDENCY_MISSING = "dependency-missing"
    HEARTBEAT_STALE = "heartbeat-stale"
    MT5_UNHEALTHY = "mt5-unhealthy"
    MARKET_DATA_UNHEALTHY = "market-data-unhealthy"
    SIGNAL_PROVIDER_UNHEALTHY = "signal-provider-unhealthy"
    EVENT_BUS_UNHEALTHY = "event-bus-unhealthy"
    DATABASE_UNHEALTHY = "database-unhealthy"
    TIMEOUT_DETECTED = "timeout-detected"
    RISK_REJECTED = "risk-rejected"
    APPROVAL_REQUIRED = "approval-required"
    ACTIVATION_PENDING = "activation-pending"
    RECONCILIATION_REQUIRED = "reconciliation-required"
    PIPELINE_ACTIVE = "pipeline-active"
    RECOVERY_REQUIRED = "recovery-required"
    PAUSED = "paused"
    FAILED = "failed"


class ComponentHealth(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    healthy: bool
    heartbeat_age_seconds: float = Field(ge=0)
    timeout_seconds: float = Field(gt=0, default=30)
    detail: str | None = Field(default=None, max_length=500)


class PipelineAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=100)
    strategy_runtime_active: bool
    dependencies_complete: bool = True
    components: list[ComponentHealth] = Field(default_factory=list)
    risk_brain_blocked: bool = False
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    human_approved: bool = False
    activation_dispatched: bool = False
    activation_acknowledged: bool = False
    runtime_reconciled: bool = False
    recovery_plan_defined: bool = False
    pause_requested: bool = False
    terminal_error: str | None = Field(default=None, max_length=1000)


class PipelineExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    human_approved: bool | None = None
    activation_dispatched: bool | None = None
    activation_acknowledged: bool | None = None
    runtime_reconciled: bool | None = None
    recovery_plan_defined: bool | None = None
    pause_requested: bool | None = None
    terminal_error: str | None = Field(default=None, max_length=1000)


class PipelineAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    state: PipelineState
    reasons: list[str] = Field(default_factory=list)
    payload: PipelineAssessmentCreate
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PipelineStatus(BaseModel):
    workspace_id: str
    latest_state: PipelineState | None = None
    count: int = 0


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    record_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
