from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class SignalDomain(str, Enum):
    HEALTH = "health"
    INCIDENT = "incident"
    COMPLIANCE = "compliance"
    ASSET = "asset"
    BACKUP = "backup"
    CHANGE = "change"
    SERVICE = "service"
    AGENT = "agent"
    TRADING = "trading"
    WORKFLOW = "workflow"


class SignalState(str, Enum):
    HEALTHY = "healthy"
    INFO = "info"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SignalCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    reporter_id: str = Field(min_length=1, max_length=120)
    module: str = Field(min_length=1, max_length=120)
    domain: SignalDomain
    signal_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    title: str = Field(min_length=1, max_length=300)
    state: SignalState
    priority: Priority = Priority.MEDIUM
    summary: str = Field(default="", max_length=4000)
    metric_name: str = Field(default="", max_length=120)
    metric_value: float | None = None
    unit: str = Field(default="", max_length=40)
    entity_id: str = Field(default="", max_length=180)
    action_url: str = Field(default="", max_length=1000)
    labels: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    human_approved: bool = True
    execute_action: bool = False

    @model_validator(mode="after")
    def safety(self) -> "SignalCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_action:
            raise ValueError("command center signals never execute actions")
        return self


class SignalRecord(SignalCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DashboardFilter(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    domains: list[SignalDomain] = Field(default_factory=list)
    states: list[SignalState] = Field(default_factory=list)
    priorities: list[Priority] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=200)


class DomainSummary(BaseModel):
    domain: SignalDomain
    total: int
    critical: int
    warning_or_degraded: int
    healthy: int
    score: float = Field(ge=0, le=100)


class CommandCenterOverview(BaseModel):
    workspace_id: str
    overall_state: SignalState
    readiness_score: float = Field(ge=0, le=100)
    total_signals: int
    critical_signals: int
    warning_signals: int
    offline_signals: int
    healthy_signals: int
    domains: list[DomainSummary]
    top_priorities: list[SignalRecord]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TimelinePoint(BaseModel):
    observed_at: datetime
    signal_id: UUID
    domain: SignalDomain
    state: SignalState
    priority: Priority
    title: str


class CommandCenterMetrics(BaseModel):
    workspace_id: str
    signal_records: int
    monitored_modules: int
    monitored_domains: int
    critical_items: int
    readiness_score: float = Field(ge=0, le=100)


class CommandCenterStatus(BaseModel):
    version: str = "11.3"
    read_only_aggregation: bool = True
    automatic_actions: bool = False
    external_execution: bool = False
    automatic_remediation: bool = False
    human_approval_required: bool = True
