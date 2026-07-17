from datetime import datetime, time, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ScheduleState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class TriggerKind(str, Enum):
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"


class MisfirePolicy(str, Enum):
    SKIP = "skip"
    FIRE_ONCE = "fire-once"
    CATCH_UP_PLAN = "catch-up-plan"


class RunState(str, Enum):
    PLANNED = "planned"
    RELEASED = "released"
    SKIPPED = "skipped"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduleCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    schedule_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=4000)
    trigger_kind: TriggerKind
    timezone_name: str = Field(default="UTC", min_length=1, max_length=120)
    run_at: datetime | None = None
    interval_seconds: int | None = Field(default=None, ge=60, le=31536000)
    cron_expression: str | None = Field(default=None, max_length=120)
    start_at: datetime | None = None
    end_at: datetime | None = None
    allowed_weekdays: list[int] = Field(default_factory=list, max_length=7)
    window_start: time | None = None
    window_end: time | None = None
    misfire_policy: MisfirePolicy = MisfirePolicy.SKIP
    max_catch_up_runs: int = Field(default=1, ge=1, le=100)
    target_type: str = Field(min_length=1, max_length=160)
    target_reference: str = Field(min_length=1, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_activation: bool = False
    execute_target: bool = False
    external_scheduler: bool = False

    @model_validator(mode="after")
    def validate_schedule(self) -> "ScheduleCreate":
        configured = {
            TriggerKind.ONCE: self.run_at is not None and self.interval_seconds is None and self.cron_expression is None,
            TriggerKind.INTERVAL: self.interval_seconds is not None and self.run_at is None and self.cron_expression is None,
            TriggerKind.CRON: self.cron_expression is not None and self.run_at is None and self.interval_seconds is None,
        }
        if not configured[self.trigger_kind]:
            raise ValueError("trigger configuration does not match trigger_kind")
        if self.end_at and self.start_at and self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        if any(day < 0 or day > 6 for day in self.allowed_weekdays):
            raise ValueError("allowed_weekdays must use values 0 through 6")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_activation:
            raise ValueError("automatic schedule activation is disabled")
        if self.execute_target:
            raise ValueError("scheduler planning never executes target actions")
        if self.external_scheduler:
            raise ValueError("external scheduler providers are disabled")
        return self


class ScheduleRecord(ScheduleCreate):
    id: UUID = Field(default_factory=uuid4)
    state: ScheduleState = ScheduleState.DRAFT
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    run_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Mutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=3000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "Mutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class TickRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    evaluation_time: datetime | None = None
    human_approved: bool = True
    automatic_release: bool = False
    execute_targets: bool = False

    @model_validator(mode="after")
    def planning_only(self) -> "TickRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_release:
            raise ValueError("automatic schedule release is disabled")
        if self.execute_targets:
            raise ValueError("scheduler ticks never execute target actions")
        return self


class ManualTriggerRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=3000)
    human_approved: bool = True
    execute_target: bool = False

    @model_validator(mode="after")
    def planning_only(self) -> "ManualTriggerRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_target:
            raise ValueError("manual triggers create plans only")
        return self


class RunRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    schedule_id: UUID
    planned_for: datetime
    trigger_source: str
    state: RunState = RunState.PLANNED
    target_type: str
    target_reference: str
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str
    reason: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SchedulerMetrics(BaseModel):
    workspace_id: str
    schedules: int
    active_schedules: int
    paused_schedules: int
    planned_runs: int
    skipped_runs: int
    completed_runs: int
    failed_runs: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    entity_type: str
    entity_id: UUID | None = None
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SchedulerStatus(BaseModel):
    version: str = "9.9"
    schedules: int
    runs: int
    active_schedules: int
    automatic_activation_enabled: bool = False
    automatic_release_enabled: bool = False
    external_scheduler_enabled: bool = False
    executes_actions: bool = False
