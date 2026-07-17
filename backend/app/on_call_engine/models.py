from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ScheduleState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class EscalationState(str, Enum):
    PLANNED = "planned"
    NOTIFIED = "notified"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class CoverageState(str, Enum):
    COVERED = "covered"
    GAP = "gap"
    OVERLAP = "overlap"


class RotationMember(BaseModel):
    user_id: str = Field(min_length=1, max_length=120)
    position: int = Field(ge=0, le=10000)
    role: str = Field(default="primary", min_length=1, max_length=120)


class EscalationLevel(BaseModel):
    level: int = Field(ge=1, le=20)
    target_user_ids: list[str] = Field(min_length=1, max_length=100)
    acknowledge_within_seconds: int = Field(default=300, ge=30, le=86400)


class ScheduleCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    schedule_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=300)
    service_keys: list[str] = Field(default_factory=list, max_length=500)
    timezone_name: str = Field(default="UTC", min_length=1, max_length=120)
    rotation_members: list[RotationMember] = Field(min_length=1, max_length=500)
    shift_duration_seconds: int = Field(default=604800, ge=3600, le=31536000)
    rotation_start: datetime
    escalation_levels: list[EscalationLevel] = Field(min_length=1, max_length=20)
    labels: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_activation: bool = False
    notify_external: bool = False
    execute_response: bool = False
    external_provider: bool = False

    @model_validator(mode="after")
    def validate_schedule(self) -> "ScheduleCreate":
        positions = [member.position for member in self.rotation_members]
        if len(positions) != len(set(positions)):
            raise ValueError("rotation positions must be unique")
        levels = [item.level for item in self.escalation_levels]
        if levels != list(range(1, len(levels) + 1)):
            raise ValueError("escalation levels must be consecutive starting at 1")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_activation:
            raise ValueError("automatic on-call schedule activation is disabled")
        if self.notify_external:
            raise ValueError("automatic external paging is disabled")
        if self.execute_response:
            raise ValueError("on-call records never execute response actions")
        if self.external_provider:
            raise ValueError("external on-call providers are disabled")
        return self


class ScheduleRecord(ScheduleCreate):
    id: UUID = Field(default_factory=uuid4)
    state: ScheduleState = ScheduleState.DRAFT
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


class HandoverCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    schedule_id: UUID
    from_user_id: str = Field(min_length=1, max_length=120)
    to_user_id: str = Field(min_length=1, max_length=120)
    start_at: datetime
    end_at: datetime
    reason: str = Field(default="", max_length=4000)
    human_approved: bool = True
    automatic_handover: bool = False

    @model_validator(mode="after")
    def validate_handover(self) -> "HandoverCreate":
        if self.end_at <= self.start_at:
            raise ValueError("handover end_at must be after start_at")
        if self.from_user_id == self.to_user_id:
            raise ValueError("handover users must differ")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_handover:
            raise ValueError("automatic handovers are disabled")
        return self


class HandoverRecord(HandoverCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EscalationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    schedule_id: UUID
    incident_id: UUID | None = None
    subject: str = Field(min_length=1, max_length=300)
    correlation_id: str = Field(min_length=1, max_length=240)
    human_approved: bool = True
    notify_external: bool = False
    execute_response: bool = False

    @model_validator(mode="after")
    def safety(self) -> "EscalationCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.notify_external:
            raise ValueError("escalation plans never send external pages")
        if self.execute_response:
            raise ValueError("escalation plans never execute response actions")
        return self


class EscalationRecord(EscalationCreate):
    id: UUID = Field(default_factory=uuid4)
    state: EscalationState = EscalationState.PLANNED
    current_level: int = 1
    assigned_user_ids: list[str] = Field(default_factory=list)
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    next_escalation_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AcknowledgeCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    escalation_id: UUID
    note: str = Field(default="", max_length=4000)
    human_approved: bool = True


class CoverageRecord(BaseModel):
    workspace_id: str
    schedule_id: UUID
    evaluated_at: datetime
    active_user_ids: list[str]
    state: CoverageState
    handover_ids: list[UUID] = Field(default_factory=list)


class MetricsRecord(BaseModel):
    workspace_id: str
    schedules: int
    active_schedules: int
    planned_escalations: int
    acknowledged_escalations: int
    escalated_events: int
    unresolved_escalations: int
    handovers: int
    coverage_gaps: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    entity_type: str
    entity_id: UUID | None = None
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OnCallStatus(BaseModel):
    version: str = "10.5"
    schedules: int
    escalations: int
    handovers: int
    automatic_activation_enabled: bool = False
    external_paging_enabled: bool = False
    executes_response_actions: bool = False
    external_provider_enabled: bool = False
