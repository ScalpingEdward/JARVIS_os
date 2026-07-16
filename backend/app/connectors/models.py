from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ConnectorKind(str, Enum):
    mt5 = "mt5"
    tradingview = "tradingview"
    telegram = "telegram"
    gmail = "gmail"
    google_calendar = "google_calendar"
    github = "github"
    obsidian = "obsidian"
    notion = "notion"
    slack = "slack"
    discord = "discord"
    local_files = "local_files"
    rest_api = "rest_api"
    mcp = "mcp"
    docker = "docker"
    local_program = "local_program"


class ConnectorState(str, Enum):
    disabled = "disabled"
    connecting = "connecting"
    healthy = "healthy"
    degraded = "degraded"
    disconnected = "disconnected"
    paused = "paused"
    error = "error"


class ConnectorPermission(str, Enum):
    read = "read"
    write = "write"
    execute = "execute"


class ConnectorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: ConnectorKind
    permissions: set[ConnectorPermission] = Field(default_factory=lambda: {ConnectorPermission.read})
    secret_refs: list[str] = Field(default_factory=list)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10000)
    auto_reconnect: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)


class ConnectorRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    kind: ConnectorKind
    state: ConnectorState = ConnectorState.disabled
    permissions: set[ConnectorPermission]
    secret_refs: list[str]
    rate_limit_per_minute: int
    auto_reconnect: bool
    metadata: dict[str, str]
    last_health_check_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectorAction(BaseModel):
    action: str
    actor: str = "human"
    reason: str | None = None


class ConnectorHealthUpdate(BaseModel):
    healthy: bool
    latency_ms: int | None = Field(default=None, ge=0)
    error: str | None = None


class ConnectorListResponse(BaseModel):
    items: list[ConnectorRecord]
    count: int


class ConnectorPlatformStatus(BaseModel):
    total: int
    healthy: int
    degraded: int
    paused: int
    disconnected: int
    automatic_order_execution: bool = False
    automatic_merge: bool = False


class ConnectorAuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    connector_id: UUID
    event: str
    actor: str
    details: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
