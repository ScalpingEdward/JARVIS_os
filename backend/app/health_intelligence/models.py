from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class TargetKind(str, Enum):
    SYSTEM = "system"
    SERVICE = "service"
    AGENT = "agent"
    ASSET = "asset"
    WORKFLOW = "workflow"


class HealthState(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class AgentState(str, Enum):
    RUNNING = "running"
    IDLE = "idle"
    BUSY = "busy"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    OFFLINE = "offline"


class MetricKind(str, Enum):
    CPU_PERCENT = "cpu-percent"
    MEMORY_PERCENT = "memory-percent"
    DISK_PERCENT = "disk-percent"
    NETWORK_LATENCY_MS = "network-latency-ms"
    API_LATENCY_MS = "api-latency-ms"
    ERROR_RATE_PERCENT = "error-rate-percent"
    QUEUE_LENGTH = "queue-length"
    UPTIME_PERCENT = "uptime-percent"
    HEARTBEAT_AGE_SECONDS = "heartbeat-age-seconds"
    CUSTOM = "custom"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class TelemetryCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    reporter_id: str = Field(min_length=1, max_length=120)
    target_kind: TargetKind
    target_key: str = Field(min_length=1, max_length=240)
    metric_kind: MetricKind
    value: float
    unit: str = Field(default="", max_length=80)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    labels: dict[str, str] = Field(default_factory=dict)
    human_approved: bool = True
    execute_action: bool = False
    external_collector: bool = False

    @model_validator(mode="after")
    def safety(self) -> "TelemetryCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_action:
            raise ValueError("telemetry records never execute operational actions")
        if self.external_collector:
            raise ValueError("external telemetry collectors are disabled")
        return self


class TelemetryRecord(TelemetryCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HealthRuleCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    rule_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=300)
    target_kind: TargetKind
    metric_kind: MetricKind
    warning_threshold: float
    critical_threshold: float
    higher_is_worse: bool = True
    stale_after_seconds: int | None = Field(default=None, ge=1, le=604800)
    enabled: bool = True
    human_approved: bool = True
    automatic_remediation: bool = False

    @model_validator(mode="after")
    def validate_rule(self) -> "HealthRuleCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_remediation:
            raise ValueError("automatic remediation is disabled")
        if self.higher_is_worse and self.warning_threshold > self.critical_threshold:
            raise ValueError("warning threshold must not exceed critical threshold")
        if not self.higher_is_worse and self.warning_threshold < self.critical_threshold:
            raise ValueError("warning threshold must not be below critical threshold")
        return self


class HealthRuleRecord(HealthRuleCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HealthSnapshot(BaseModel):
    workspace_id: str
    target_kind: TargetKind
    target_key: str
    state: HealthState
    metric_kind: MetricKind
    value: float | None = None
    reason: str
    observed_at: datetime | None = None


class AlertState(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class AlertRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    target_kind: TargetKind
    target_key: str
    metric_kind: MetricKind
    severity: Severity
    state: AlertState = AlertState.OPEN
    title: str
    description: str
    observed_value: float | None = None
    rule_id: UUID | None = None
    acknowledged_by: str | None = None
    resolved_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Mutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=4000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "Mutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class MetricsRecord(BaseModel):
    workspace_id: str
    telemetry_records: int
    health_rules: int
    open_alerts: int
    critical_alerts: int
    monitored_targets: int


class HealthIntelligenceStatus(BaseModel):
    version: str = "11.1"
    automatic_restart: bool = False
    process_kill: bool = False
    automatic_scaling: bool = False
    infrastructure_mutation: bool = False
    external_collectors: bool = False
    human_approval_required: bool = True
