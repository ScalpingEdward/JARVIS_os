from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class IntegrationKind(StrEnum):
    mt5 = "mt5"
    tradingview = "tradingview"
    telegram = "telegram"
    research = "research"


class IntegrationState(StrEnum):
    disconnected = "disconnected"
    connecting = "connecting"
    online = "online"
    degraded = "degraded"
    error = "error"


class LiveIntegrationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    kind: IntegrationKind
    endpoint: str | None = Field(default=None, max_length=500)
    account_label: str | None = Field(default=None, max_length=120)
    symbols: list[str] = Field(default_factory=list, max_length=50)
    read_only: bool = True
    enabled: bool = True
    poll_seconds: int = Field(default=15, ge=1, le=3600)


class IntegrationHeartbeat(BaseModel):
    state: IntegrationState
    latency_ms: float | None = Field(default=None, ge=0)
    records_received: int = Field(default=0, ge=0)
    last_error: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class LiveIntegration(LiveIntegrationCreate):
    id: UUID = Field(default_factory=uuid4)
    state: IntegrationState = IntegrationState.disconnected
    latency_ms: float | None = None
    records_received: int = 0
    last_error: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    last_heartbeat_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LiveIntegrationList(BaseModel):
    items: list[LiveIntegration]
    count: int


class NormalizedMarketEvent(BaseModel):
    source: IntegrationKind
    symbol: str = Field(min_length=1, max_length=40)
    event_type: str = Field(min_length=1, max_length=80)
    timeframe: str | None = Field(default=None, max_length=20)
    price: float | None = None
    volume: float | None = None
    payload: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IntegrationHubStatus(BaseModel):
    total: int
    online: int
    degraded: int
    disconnected: int
    errors: int
    records_received: int
    read_only_enforced: bool = True
    automatic_order_execution: bool = False
    automatic_merge: bool = False
