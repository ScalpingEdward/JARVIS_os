from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PluginState(str, Enum):
    REGISTERED = "registered"
    ACTIVE = "active"
    DISABLED = "disabled"
    DEGRADED = "degraded"
    QUARANTINED = "quarantined"


class PermissionRisk(str, Enum):
    READ = "read"
    WRITE = "write"
    EXTERNAL = "external"
    CRITICAL = "critical"


class PermissionGrant(BaseModel):
    permission: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9_.:-]+$")
    risk: PermissionRisk = PermissionRisk.READ
    granted: bool = False
    requires_human_approval: bool = True


class PluginManifest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    plugin_key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=40)
    author: str = Field(min_length=1, max_length=200)
    api_version: str = Field(default="1.0", min_length=1, max_length=40)
    minimum_core_version: str = Field(default="7.9", min_length=1, max_length=40)
    maximum_core_version: str | None = Field(default=None, max_length=40)
    capabilities: list[str] = Field(min_length=1, max_length=100)
    permissions: list[PermissionGrant] = Field(default_factory=list, max_length=100)
    dependencies: list[str] = Field(default_factory=list, max_length=100)
    subscriptions: list[str] = Field(default_factory=list, max_length=100)
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    memory_limit_mb: int = Field(default=256, ge=32, le=4096)
    human_approved: bool = True
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "PluginManifest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_external_action:
            raise ValueError("automatic external actions are disabled")
        return self


class PluginRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    plugin_key: str
    name: str
    version: str
    author: str
    api_version: str
    minimum_core_version: str
    maximum_core_version: str | None
    capabilities: list[str]
    permissions: list[PermissionGrant]
    dependencies: list[str]
    subscriptions: list[str]
    timeout_seconds: int
    memory_limit_mb: int
    state: PluginState = PluginState.REGISTERED
    health_message: str = "Not activated"
    invocation_count: int = 0
    failure_count: int = 0
    last_heartbeat_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PluginMutation(BaseModel):
    human_approved: bool = True
    reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def require_approval(self) -> "PluginMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class PermissionUpdate(BaseModel):
    permission: str = Field(min_length=1, max_length=120)
    granted: bool
    human_approved: bool = True

    @model_validator(mode="after")
    def require_approval(self) -> "PermissionUpdate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class PluginInvocation(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    capability: str = Field(min_length=1, max_length=120)
    input: dict[str, Any] = Field(default_factory=dict)
    requested_permissions: list[str] = Field(default_factory=list, max_length=100)
    external_action: bool = False
    human_approved: bool = True

    @model_validator(mode="after")
    def enforce_invocation_safety(self) -> "PluginInvocation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.external_action:
            raise ValueError("automatic external actions are disabled")
        return self


class InvocationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    plugin_id: UUID
    capability: str
    input: dict[str, Any]
    requested_permissions: list[str]
    permitted: bool
    sandboxed: bool = True
    external_action: bool = False
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventPublish(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    publisher_id: str = Field(min_length=1, max_length=120)
    event_type: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.:-]+$")
    payload: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    external_action: bool = False

    @model_validator(mode="after")
    def enforce_event_safety(self) -> "EventPublish":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.external_action:
            raise ValueError("automatic external actions are disabled")
        return self


class EventRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    publisher_id: str
    event_type: str
    payload: dict[str, Any]
    subscriber_plugin_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PluginSDKStatus(BaseModel):
    service: str = "plugin-sdk"
    version: str = "7.9"
    registered_plugins: int
    active_plugins: int
    degraded_plugins: int
    quarantined_plugins: int
    total_capabilities: int
    published_events: int
    sandbox_enforced: bool = True
    automatic_external_actions: bool = False
    workspace_isolation_enabled: bool = True
