from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IncidentState(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class SwitchState(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class MetricCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_module: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=240)
    value: float
    unit: str = Field(default="", max_length=40)
    labels: dict[str, str] = Field(default_factory=dict)
    human_approved: bool = True
    export_external: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "MetricCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.export_external:
            raise ValueError("external metric export is disabled in v8.9")
        return self


class MetricRecord(MetricCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TraceCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    trace_id: str = Field(min_length=1, max_length=200)
    span_id: str = Field(min_length=1, max_length=200)
    parent_span_id: str | None = Field(default=None, max_length=200)
    source_module: str = Field(min_length=1, max_length=160)
    operation: str = Field(min_length=1, max_length=300)
    duration_ms: float = Field(ge=0)
    success: bool = True
    attributes: dict[str, Any] = Field(default_factory=dict)
    capture_secrets: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "TraceCreate":
        if self.capture_secrets:
            raise ValueError("secret capture is disabled")
        return self


class TraceRecord(TraceCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AlertCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    source_module: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=300)
    severity: Severity
    condition: str = Field(min_length=1, max_length=2000)
    human_approved: bool = True
    automatic_external_notification: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "AlertCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_external_notification:
            raise ValueError("automatic external notifications are disabled")
        return self


class AlertRecord(AlertCreate):
    id: UUID = Field(default_factory=uuid4)
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncidentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    source_module: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=5000)
    severity: Severity
    correlation_id: str | None = Field(default=None, max_length=200)
    human_approved: bool = True
    autonomous_remediation: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "IncidentCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.autonomous_remediation:
            raise ValueError("autonomous remediation is disabled")
        return self


class IncidentRecord(IncidentCreate):
    id: UUID = Field(default_factory=uuid4)
    state: IncidentState = IncidentState.OPEN
    acknowledged_by: str | None = None
    resolved_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SLOCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    module_key: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=240)
    target_percent: float = Field(gt=0, le=100)
    window_minutes: int = Field(ge=1, le=525600)
    human_approved: bool = True


class SLORecord(SLOCreate):
    id: UUID = Field(default_factory=uuid4)
    current_percent: float = 100.0
    breached: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ControlSwitchCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    module_key: str = Field(min_length=1, max_length=160)
    reason: str = Field(default="", max_length=1000)
    human_approved: bool = True
    execute_shutdown: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "ControlSwitchCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_shutdown:
            raise ValueError("real module shutdown is disabled in v8.9")
        return self


class ControlSwitchRecord(ControlSwitchCreate):
    id: UUID = Field(default_factory=uuid4)
    state: SwitchState = SwitchState.ENABLED
    applied: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OperatorMutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=1000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "OperatorMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
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


class ObservabilityStatus(BaseModel):
    service: str = "observability-control"
    version: str = "8.9"
    metrics: int
    traces: int
    alerts: int
    incidents: int
    open_incidents: int
    slos: int
    switches: int
    external_export_enabled: bool = False
    autonomous_remediation_enabled: bool = False
    real_shutdown_enabled: bool = False
