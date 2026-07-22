from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class RuntimeState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CIRCUIT_OPEN = "circuit-open"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    ARCHIVED = "archived"


class HealthState(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class RuntimeDependency(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    required: bool = True
    health: HealthState = HealthState.UNKNOWN
    last_heartbeat_at: datetime | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    runtime_name: str = Field(min_length=1, max_length=120)
    broker_adapter: str = Field(pattern="^(mt5|dxtrade|ctrader|fix|rest)$")
    account_ref: str = Field(min_length=1, max_length=200)
    active_policy_record_id: str = Field(min_length=1, max_length=200)
    workflow_record_id: str = Field(min_length=1, max_length=200)
    command_record_ids: list[str] = Field(default_factory=list, max_length=100)
    heartbeat_timeout_seconds: int = Field(default=30, ge=5, le=3600)
    max_consecutive_failures: int = Field(default=3, ge=1, le=100)
    restart_limit: int = Field(default=2, ge=0, le=20)
    dependencies: list[RuntimeDependency] = Field(default_factory=list)
    risk_brain_blocked: bool = False
    upstream_evidence_verified: bool = False

    @model_validator(mode="after")
    def validate_dependencies(self) -> "RuntimeCreate":
        names = [item.name for item in self.dependencies]
        if len(names) != len(set(names)):
            raise ValueError("duplicate runtime dependency")
        return self


class RuntimeAction(BaseModel):
    action: str = Field(pattern="^(approve|start|heartbeat|degrade|open-circuit|restart|stop|fail|archive)$")
    actor_id: str = Field(min_length=1, max_length=120)
    approval_token: str | None = Field(default=None, max_length=300)
    receipt_id: str | None = Field(default=None, max_length=300)
    dependency_updates: list[RuntimeDependency] = Field(default_factory=list)
    reason: str | None = Field(default=None, max_length=1000)


class RuntimeRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    runtime_name: str
    broker_adapter: str
    account_ref: str
    active_policy_record_id: str
    workflow_record_id: str
    command_record_ids: list[str]
    heartbeat_timeout_seconds: int
    max_consecutive_failures: int
    restart_limit: int
    restart_count: int = 0
    consecutive_failures: int = 0
    dependencies: list[RuntimeDependency]
    state: RuntimeState
    risk_brain_blocked: bool
    upstream_evidence_verified: bool
    approval_token_hash: str | None = None
    last_receipt_id: str | None = None
    last_heartbeat_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditEvent(BaseModel):
    event_id: str
    record_id: str
    workspace_id: str
    action: str
    actor_id: str
    state: RuntimeState
    reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
