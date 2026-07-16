from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AlertSeverity(StrEnum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertDomain(StrEnum):
    trading = "trading"
    research = "research"
    system = "system"
    project = "project"
    finance = "finance"
    legal = "legal"
    health = "health"
    personal = "personal"


class AlertStatus(StrEnum):
    new = "new"
    acknowledged = "acknowledged"
    snoozed = "snoozed"
    resolved = "resolved"
    suppressed = "suppressed"


class OperationsEventCreate(BaseModel):
    source: str = Field(min_length=2, max_length=80)
    domain: AlertDomain
    title: str = Field(min_length=2, max_length=240)
    summary: str = Field(min_length=2, max_length=2000)
    severity: AlertSeverity = AlertSeverity.info
    confidence: float = Field(default=1.0, ge=0, le=1)
    urgency: float = Field(default=0.5, ge=0, le=1)
    impact: float = Field(default=0.5, ge=0, le=1)
    requires_human_approval: bool = False
    deduplication_key: str | None = Field(default=None, max_length=200)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class OperationsAlert(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str
    domain: AlertDomain
    title: str
    summary: str
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.new
    priority_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    requires_human_approval: bool = False
    executive_message: str
    deduplication_key: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class AlertStatusUpdate(BaseModel):
    status: AlertStatus


class AlertList(BaseModel):
    items: list[OperationsAlert]
    count: int


class OperationsStatus(BaseModel):
    total_alerts: int
    open_alerts: int
    critical_alerts: int
    pending_approvals: int
    suppressed_duplicates: int
    automatic_execution: bool = False
    automatic_order_execution: bool = False
    owner_salutation: str = "MASTER Brano"
