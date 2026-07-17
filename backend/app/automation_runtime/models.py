from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ConnectorType(str, Enum):
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    GMAIL = "gmail"
    CALENDAR = "calendar"
    BROWSER = "browser"
    DOCUMENTS = "documents"
    TELEGRAM = "telegram"
    GENERIC = "generic"


class ConnectorState(str, Enum):
    REGISTERED = "registered"
    ACTIVE = "active"
    DEGRADED = "degraded"
    DISABLED = "disabled"


class JobState(str, Enum):
    QUEUED = "queued"
    WAITING_APPROVAL = "waiting_approval"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class ConnectorRegister(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    connector_key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9_.-]+$")
    connector_type: ConnectorType
    display_name: str = Field(min_length=1, max_length=200)
    capabilities: list[str] = Field(min_length=1, max_length=100)
    actions: list[str] = Field(min_length=1, max_length=100)
    rate_limit_per_minute: int = Field(default=30, ge=1, le=10000)
    supports_dry_run: bool = True
    human_approved: bool = True

    @model_validator(mode="after")
    def require_approval(self) -> "ConnectorRegister":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class ConnectorRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    connector_key: str
    connector_type: ConnectorType
    display_name: str
    capabilities: list[str]
    actions: list[str]
    rate_limit_per_minute: int
    supports_dry_run: bool
    state: ConnectorState = ConnectorState.REGISTERED
    health_message: str = "Not activated"
    calls_in_current_window: int = 0
    rate_window_started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectorMutation(BaseModel):
    human_approved: bool = True
    reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def require_approval(self) -> "ConnectorMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class AutomationJobCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    connector_id: UUID
    action: str = Field(min_length=1, max_length=160)
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=200)
    dry_run: bool = True
    requires_human_approval: bool = True
    human_approved: bool = False
    external_action: bool = False
    max_retries: int = Field(default=2, ge=0, le=20)

    @model_validator(mode="after")
    def enforce_safety(self) -> "AutomationJobCreate":
        if self.external_action:
            raise ValueError("automatic external actions are disabled")
        if not self.dry_run:
            raise ValueError("v8.0 only permits dry-run jobs")
        return self


class AutomationJobRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    requester_id: str
    connector_id: UUID
    action: str
    payload: dict[str, Any]
    idempotency_key: str
    dry_run: bool = True
    requires_human_approval: bool = True
    human_approved: bool = False
    state: JobState
    retry_count: int = 0
    max_retries: int = 2
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    blocked_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JobApproval(BaseModel):
    approved: bool
    approved_by: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=500)


class JobCompletion(BaseModel):
    success: bool
    result: dict[str, Any] = Field(default_factory=dict)
    error: str = Field(default="", max_length=5000)


class RuntimeStatus(BaseModel):
    service: str = "automation-runtime"
    version: str = "8.0"
    registered_connectors: int
    active_connectors: int
    queued_jobs: int
    waiting_approval_jobs: int
    running_jobs: int
    completed_jobs: int
    failed_jobs: int
    blocked_jobs: int
    dry_run_only: bool = True
    automatic_external_actions: bool = False
    idempotency_enabled: bool = True
    rate_limiting_enabled: bool = True
