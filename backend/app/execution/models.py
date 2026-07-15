from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.planner.models import ExecutionPlan


class WorkflowStatus(StrEnum):
    created = "created"
    running = "running"
    waiting_approval = "waiting_approval"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class StepExecutionStatus(StrEnum):
    pending = "pending"
    ready = "ready"
    queued = "queued"
    running = "running"
    waiting_approval = "waiting_approval"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class WorkflowCreate(BaseModel):
    plan: ExecutionPlan
    auto_dispatch: bool = True
    max_parallel_steps: int = Field(default=2, ge=1, le=20)
    stop_on_failure: bool = True


class StepExecutionRecord(BaseModel):
    step_id: UUID
    title: str
    status: StepExecutionStatus = StepExecutionStatus.pending
    runtime_run_id: UUID | None = None
    approval_granted: bool = False
    output: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class WorkflowRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    plan: ExecutionPlan
    status: WorkflowStatus = WorkflowStatus.created
    auto_dispatch: bool = True
    max_parallel_steps: int = 2
    stop_on_failure: bool = True
    steps: list[StepExecutionRecord]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkflowListResponse(BaseModel):
    items: list[WorkflowRecord]
    count: int


class WorkflowTickResponse(BaseModel):
    workflow: WorkflowRecord
    queued_step_ids: list[UUID] = Field(default_factory=list)
    waiting_approval_step_ids: list[UUID] = Field(default_factory=list)
