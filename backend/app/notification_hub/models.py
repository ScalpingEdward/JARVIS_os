from datetime import datetime, time, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DeliveryChannel(StrEnum):
    dashboard = "dashboard"
    telegram = "telegram"
    email = "email"
    mobile_push = "mobile_push"
    voice = "voice"


class DeliveryPriority(StrEnum):
    low = "low"
    normal = "normal"
    high = "high"
    critical = "critical"


class DeliveryState(StrEnum):
    queued = "queued"
    deferred = "deferred"
    delivered = "delivered"
    acknowledged = "acknowledged"
    failed = "failed"
    cancelled = "cancelled"


class QuietHours(BaseModel):
    enabled: bool = True
    start: time = time(22, 30)
    end: time = time(7, 0)
    timezone: str = "Europe/Berlin"
    allow_critical: bool = True


class NotificationPreferences(BaseModel):
    owner_name: str = "MASTER Brano"
    default_channels: list[DeliveryChannel] = Field(default_factory=lambda: [DeliveryChannel.dashboard])
    high_priority_channels: list[DeliveryChannel] = Field(
        default_factory=lambda: [DeliveryChannel.dashboard, DeliveryChannel.telegram]
    )
    critical_channels: list[DeliveryChannel] = Field(
        default_factory=lambda: [DeliveryChannel.dashboard, DeliveryChannel.telegram, DeliveryChannel.voice]
    )
    quiet_hours: QuietHours = Field(default_factory=QuietHours)
    escalation_minutes: int = Field(default=10, ge=1, le=240)


class NotificationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    message: str = Field(min_length=1, max_length=4000)
    priority: DeliveryPriority = DeliveryPriority.normal
    domain: str = Field(default="system", max_length=80)
    source_id: str | None = Field(default=None, max_length=200)
    channels: list[DeliveryChannel] | None = None
    requires_acknowledgement: bool = False
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class DeliveryAttempt(BaseModel):
    channel: DeliveryChannel
    state: DeliveryState
    attempted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    detail: str | None = None


class NotificationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    message: str
    priority: DeliveryPriority
    domain: str
    source_id: str | None = None
    channels: list[DeliveryChannel]
    state: DeliveryState = DeliveryState.queued
    requires_acknowledgement: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deliver_after: datetime | None = None
    acknowledged_at: datetime | None = None
    attempts: list[DeliveryAttempt] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class NotificationList(BaseModel):
    items: list[NotificationRecord]
    count: int


class NotificationHubStatus(BaseModel):
    queued: int
    deferred: int
    delivered: int
    awaiting_acknowledgement: int
    failed: int
    automatic_execution: bool = False
    automatic_order_execution: bool = False
    owner_name: str
