from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MT5RuntimeBridgeState(str, Enum):
    blocked = "blocked"
    activation_required = "activation-required"
    terminal_unavailable = "terminal-unavailable"
    account_mismatch = "account-mismatch"
    symbol_mapping_required = "symbol-mapping-required"
    trading_permission_required = "trading-permission-required"
    execution_probe_required = "execution-probe-required"
    approval_required = "approval-required"
    bridge_pending = "bridge-pending"
    reconciliation_required = "reconciliation-required"
    bridge_ready = "bridge-ready"


class MT5RuntimeObservation(BaseModel):
    live_adapter_state: str = "production-ready"
    terminal_process_running: bool = False
    terminal_version_verified: bool = False
    terminal_path_verified: bool = False
    account_login_verified: bool = False
    expected_account_login: int = Field(default=0, ge=0)
    observed_account_login: int = Field(default=0, ge=0)
    broker_server_verified: bool = False
    trade_mode_enabled: bool = False
    algo_trading_enabled: bool = False
    market_connected: bool = False
    symbol_mapping_verified: bool = False
    volume_step_verified: bool = False
    filling_mode_verified: bool = False
    stop_level_verified: bool = False
    execution_probe_completed: bool = False
    execution_probe_errors: int = Field(default=0, ge=0)
    execution_probe_reconciled: bool = False
    human_approval_verified: bool = False
    bridge_started: bool = False
    bridge_acknowledged: bool = False
    positions_reconciled: bool = False
    pending_orders_reconciled: bool = False
    account_snapshot_reconciled: bool = False


class MT5RuntimeBridgeCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=100)
    bridge_id: UUID = Field(default_factory=uuid4)
    terminal_reference: str = Field(min_length=1, max_length=250)
    account_reference: str = Field(min_length=1, max_length=200)
    risk_brain_clear: bool = True
    observation: MT5RuntimeObservation


class MT5RuntimeBridgeRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    bridge_id: UUID
    terminal_reference: str
    account_reference: str
    state: MT5RuntimeBridgeState
    reasons: list[str] = Field(default_factory=list)
    order_submission_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BridgeStartRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    bridge_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    human_approval_verified: bool
    bridge_started: bool
    bridge_acknowledged: bool
    positions_reconciled: bool
    pending_orders_reconciled: bool
    account_snapshot_reconciled: bool


class MT5RuntimeBridgeStatusResponse(BaseModel):
    workspace_id: str
    records: int
    bridge_ready: int
    blocked: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    bridge_id: UUID
    state: MT5RuntimeBridgeState
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
