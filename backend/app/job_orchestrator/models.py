from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class QueueState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class WorkerState(str, Enum):
    REGISTERED = "registered"
    ONLINE = "online"
    BUSY = "busy"
    DRAINING = "draining"
    OFFLINE = "offline"


class JobState(str, Enum):
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    RETRY_WAIT = "retry-wait"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD = "dead"
    CANCELLED = "cancelled"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"


class QueueCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    queue_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    description: str = Field(default="", max_length=4000)
    allowed_job_types: list[str] = Field(default_factory=list, max_length=500)
    max_concurrency: int = Field(default=10, ge=1, le=10000)
    default_lease_seconds: int = Field(default=60, ge=5, le=86400)
    human_approved: bool = True
    automatic_activation: bool = False
    external_queue: bool = False

    @model_validator(mode="after")
    def safety(self) -> "QueueCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_activation:
            raise ValueError("automatic queue activation is disabled")
        if self.external_queue:
            raise ValueError("external queue providers are disabled in v9.8")
        return self


class QueueRecord(QueueCreate):
    id: UUID = Field(default_factory=uuid4)
    state: QueueState = QueueState.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkerCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    worker_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    queue_ids: list[UUID] = Field(min_length=1, max_length=200)
    capabilities: list[str] = Field(default_factory=list, max_length=500)
    max_parallel_jobs: int = Field(default=1, ge=1, le=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    execute_jobs: bool = False
    external_worker: bool = False

    @model_validator(mode="after")
    def safety(self) -> "WorkerCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_jobs:
            raise ValueError("workers do not execute operational jobs in v9.8")
        if self.external_worker:
            raise ValueError("external worker registration is disabled")
        return self


class WorkerRecord(WorkerCreate):
    id: UUID = Field(default_factory=uuid4)
    state: WorkerState = WorkerState.REGISTERED
    active_job_ids: list[UUID] = Field(default_factory=list)
    last_heartbeat_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JobCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    queue_id: UUID
    job_type: str = Field(min_length=1, max_length=200)
    priority: Priority = Priority.NORMAL
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=240)
    correlation_id: str = Field(min_length=1, max_length=240)
    scheduled_at: datetime | None = None
    max_retries: int = Field(default=3, ge=0, le=20)
    backoff_seconds: int = Field(default=5, ge=0, le=86400)
    lease_seconds: int | None = Field(default=None, ge=5, le=86400)
    human_approved: bool = True
    execute_action: bool = False

    @model_validator(mode="after")
    def safety(self) -> "JobCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_action:
            raise ValueError("job creation never executes operational actions")
        return self


class JobRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    queue_id: UUID
    job_type: str
    priority: Priority
    payload: dict[str, Any]
    metadata: dict[str, Any]
    idempotency_key: str
    correlation_id: str
    scheduled_at: datetime | None = None
    max_retries: int
    backoff_seconds: int
    lease_seconds: int
    state: JobState = JobState.QUEUED
    retry_count: int = 0
    leased_by_worker_id: UUID | None = None
    lease_expires_at: datetime | None = None
    next_attempt_at: datetime | None = None
    result_reference: str | None = None
    failure_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Mutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=3000)
    human_approved: bool = True

    @model_validator(mode="after")
    def safety(self) -> "Mutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class Heartbeat(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    state: WorkerState = WorkerState.ONLINE
    human_approved: bool = True

    @model_validator(mode="after")
    def safety(self) -> "Heartbeat":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class LeaseRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    worker_id: UUID
    queue_id: UUID
    requester_id: str = Field(min_length=1, max_length=120)
    human_approved: bool = True
    execute_job: bool = False

    @model_validator(mode="after")
    def safety(self) -> "LeaseRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_job:
            raise ValueError("leasing is planning-only and never executes the job")
        return self


class CompletionRequest(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    success: bool
    result_reference: str | None = Field(default=None, max_length=1000)
    reason: str = Field(default="", max_length=3000)
    human_approved: bool = True

    @model_validator(mode="after")
    def safety(self) -> "CompletionRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class MetricsRecord(BaseModel):
    workspace_id: str
    queues: int
    workers: int
    online_workers: int
    queued_jobs: int
    leased_jobs: int
    retry_wait_jobs: int
    succeeded_jobs: int
    failed_jobs: int
    dead_jobs: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    entity_type: str
    entity_id: UUID | None = None
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JobOrchestratorStatus(BaseModel):
    version: str = "9.8"
    queues: int
    workers: int
    jobs: int
    dead_jobs: int
    automatic_execution_enabled: bool = False
    external_workers_enabled: bool = False
    external_queues_enabled: bool = False
    executes_actions: bool = False
