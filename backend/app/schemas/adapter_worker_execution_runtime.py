from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class AdapterWorkerState(str, Enum):
    BLOCKED = "blocked"
    PENDING = "pending"
    LEASED = "leased"
    RUNNING = "running"
    HEARTBEAT_MISSED = "heartbeat-missed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed-out"
    CANCELLED = "cancelled"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AdapterWorkerExecutionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    gateway_record_id: str = Field(min_length=1, max_length=160)
    dispatch_token: str = Field(min_length=16, max_length=512)
    adapter_id: str = Field(min_length=1, max_length=160)
    tool_name: str = Field(min_length=1, max_length=160)
    operation: str = Field(min_length=1, max_length=160)
    side_effect_level: str = Field(default="read-only")
    timeout_seconds: int = Field(default=60, ge=1, le=900)
    lease_seconds: int = Field(default=30, ge=5, le=300)
    heartbeat_interval_seconds: int = Field(default=10, ge=1, le=120)
    max_attempts: int = Field(default=2, ge=1, le=5)
    max_cost: float = Field(default=25.0, ge=0.0)
    protected_operations: List[str] = Field(
        default_factory=lambda: [
            "fund-movement",
            "order-submit",
            "trade-execute",
            "credential-mutate",
            "permission-escalate",
            "disable-safety-control",
        ]
    )

    @model_validator(mode="after")
    def validate_runtime_contract(self):
        if self.heartbeat_interval_seconds >= self.lease_seconds:
            raise ValueError("heartbeat interval must be shorter than lease duration")
        return self


class AdapterWorkerLeaseRequest(BaseModel):
    workspace_id: str = Field(min_length=1)
    worker_id: str = Field(min_length=1, max_length=160)
    operation_id: str = Field(min_length=1, max_length=200)


class AdapterWorkerHeartbeat(BaseModel):
    workspace_id: str = Field(min_length=1)
    worker_id: str = Field(min_length=1, max_length=160)
    lease_token: str = Field(min_length=16, max_length=512)
    operation_id: str = Field(min_length=1, max_length=200)


class AdapterWorkerResult(BaseModel):
    workspace_id: str = Field(min_length=1)
    worker_id: str = Field(min_length=1, max_length=160)
    lease_token: str = Field(min_length=16, max_length=512)
    operation_id: str = Field(min_length=1, max_length=200)
    status: str = Field(pattern="^(succeeded|failed|timed-out)$")
    output_digest: str = Field(min_length=1, max_length=256)
    duration_ms: int = Field(ge=0)
    cost: float = Field(default=0.0, ge=0.0)
    metadata: Dict[str, str] = Field(default_factory=dict)


class AdapterWorkerAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None


class AdapterWorkerRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    gateway_record_id: str
    adapter_id: str
    tool_name: str
    operation: str
    state: AdapterWorkerState
    assigned_worker_id: Optional[str] = None
    lease_token: Optional[str] = None
    lease_expires_at: Optional[str] = None
    last_heartbeat_at: Optional[str] = None
    attempt_count: int = 0
    result_status: Optional[str] = None
    result_digest: Optional[str] = None
    actual_cost: float = 0.0
    risk_flags: List[str] = Field(default_factory=list)
    version: int = 1
