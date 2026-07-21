from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class LiveAdapterActivationState(str, Enum):
    blocked = "blocked"
    continuity_required = "continuity-required"
    package_invalid = "package-invalid"
    secrets_required = "secrets-required"
    adapter_unhealthy = "adapter-unhealthy"
    dry_run_required = "dry-run-required"
    approval_required = "approval-required"
    activation_pending = "activation-pending"
    reconciliation_required = "reconciliation-required"
    production_ready = "production-ready"


class AdapterRuntimeObservation(BaseModel):
    continuity_state: str = "continuity-ready"
    deployment_package_signed: bool = False
    artifact_checksum_verified: bool = False
    dependency_lock_verified: bool = False
    migration_plan_verified: bool = False
    rollback_package_verified: bool = False
    secret_references_resolved: bool = False
    raw_secrets_present: bool = False
    adapter_kind: str = "mt5"
    adapter_health_verified: bool = False
    broker_session_ready: bool = False
    market_data_ready: bool = False
    executor_transport_ready: bool = False
    dry_run_completed: bool = False
    dry_run_order_count: int = Field(default=0, ge=0)
    dry_run_errors: int = Field(default=0, ge=0)
    dry_run_reconciliation_verified: bool = False
    human_approval_verified: bool = False
    activation_dispatched: bool = False
    activation_acknowledged: bool = False
    live_session_identity_verified: bool = False
    live_positions_reconciled: bool = False
    live_pending_orders_reconciled: bool = False
    health_probe_registered: bool = False
    rollback_probe_registered: bool = False


class LiveAdapterActivationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=100)
    deployment_id: UUID = Field(default_factory=uuid4)
    environment: str = "production"
    adapter_reference: str = Field(min_length=1, max_length=200)
    risk_brain_clear: bool = True
    observation: AdapterRuntimeObservation


class LiveAdapterActivationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    deployment_id: UUID
    environment: str
    adapter_reference: str
    state: LiveAdapterActivationState
    reasons: list[str] = Field(default_factory=list)
    production_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ActivationRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    deployment_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    human_approval_verified: bool
    activation_dispatched: bool
    activation_acknowledged: bool
    live_session_identity_verified: bool
    live_positions_reconciled: bool
    live_pending_orders_reconciled: bool


class ActivationStatusResponse(BaseModel):
    workspace_id: str
    records: int
    production_ready: int
    blocked: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    deployment_id: UUID
    state: LiveAdapterActivationState
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
