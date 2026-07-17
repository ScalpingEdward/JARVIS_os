from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ModuleHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class EventPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EventState(str, Enum):
    ACCEPTED = "accepted"
    RATE_LIMITED = "rate_limited"
    REPLAYED = "replayed"


class CommandState(str, Enum):
    PLANNED = "planned"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class ModuleRegistrationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    module_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=240)
    version: str = Field(min_length=1, max_length=80)
    capabilities: list[str] = Field(default_factory=list, max_length=300)
    published_events: list[str] = Field(default_factory=list, max_length=300)
    accepted_commands: list[str] = Field(default_factory=list, max_length=300)
    health: ModuleHealth = ModuleHealth.HEALTHY
    rate_limit_per_minute: int = Field(default=120, ge=1, le=100000)
    failure_threshold: int = Field(default=3, ge=1, le=1000)
    human_approved: bool = True
    external_endpoint: str | None = Field(default=None, max_length=2000)
    automatic_external_connection: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "ModuleRegistrationCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.external_endpoint or self.automatic_external_connection:
            raise ValueError("automatic external integrations are disabled in v8.8")
        return self


class ModuleRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    module_key: str
    name: str
    version: str
    capabilities: list[str]
    published_events: list[str]
    accepted_commands: list[str]
    health: ModuleHealth
    rate_limit_per_minute: int
    failure_threshold: int
    failure_count: int = 0
    circuit_state: CircuitState = CircuitState.CLOSED
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IntegrationEventCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    publisher_module: str = Field(min_length=1, max_length=160)
    event_type: str = Field(min_length=1, max_length=240)
    subject: str = Field(default="", max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, max_length=200)
    causation_id: UUID | None = None
    priority: EventPriority = EventPriority.NORMAL
    human_approved: bool = True
    dispatch_external: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "IntegrationEventCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.dispatch_external:
            raise ValueError("external event dispatch is disabled in v8.8")
        return self


class IntegrationEventRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    publisher_module: str
    event_type: str
    subject: str
    payload: dict[str, Any]
    correlation_id: str | None
    causation_id: UUID | None
    priority: EventPriority
    state: EventState = EventState.ACCEPTED
    sequence: int
    replay_of: UUID | None = None
    external_dispatch_performed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SubscriptionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    subscriber_module: str = Field(min_length=1, max_length=160)
    event_types: list[str] = Field(min_length=1, max_length=300)
    command_name: str | None = Field(default=None, max_length=240)
    filters: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    human_approved: bool = True
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "SubscriptionCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_external_action:
            raise ValueError("automatic external subscription actions are disabled")
        return self


class SubscriptionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    subscriber_module: str
    event_types: list[str]
    command_name: str | None
    filters: dict[str, Any]
    enabled: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CommandCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    source_module: str = Field(min_length=1, max_length=160)
    target_module: str = Field(min_length=1, max_length=160)
    command_name: str = Field(min_length=1, max_length=240)
    arguments: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, max_length=200)
    requires_human_approval: bool = True
    human_approved: bool = False
    dry_run: bool = True
    execute_command: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "CommandCreate":
        if not self.dry_run or self.execute_command:
            raise ValueError("real command execution is disabled in v8.8")
        return self


class CommandRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    requester_id: str
    source_module: str
    target_module: str
    command_name: str
    arguments: dict[str, Any]
    correlation_id: str | None
    requires_human_approval: bool
    approved: bool = False
    state: CommandState = CommandState.PLANNED
    blocked_reason: str | None = None
    executed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalRequest(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    approved: bool
    reason: str = Field(default="", max_length=1000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "ApprovalRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class HealthUpdate(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    health: ModuleHealth
    reason: str = Field(default="", max_length=1000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "HealthUpdate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class ReplayRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    event_ids: list[UUID] = Field(min_length=1, max_length=1000)
    human_approved: bool = True
    dispatch_external: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "ReplayRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.dispatch_external:
            raise ValueError("replayed events cannot be dispatched externally")
        return self


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    object_type: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IntegrationHubStatus(BaseModel):
    service: str = "integration-hub"
    version: str = "8.8"
    modules: int
    healthy_modules: int
    degraded_modules: int
    unavailable_modules: int
    open_circuits: int
    events: int
    subscriptions: int
    commands: int
    planned_commands: int
    approved_commands: int
    external_dispatch_enabled: bool = False
    real_command_execution_enabled: bool = False
