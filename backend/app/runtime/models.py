from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class RuntimeProvider(StrEnum):
    mock = "mock"
    claude = "claude"
    openai = "openai"
    codex = "codex"
    cursor = "cursor"
    gemini = "gemini"


class RuntimeStatus(StrEnum):
    idle = "idle"
    busy = "busy"
    degraded = "degraded"
    offline = "offline"


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    retrying = "retrying"
    completed = "completed"
    failed = "failed"
    timed_out = "timed_out"


class RuntimeWorkerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: RuntimeProvider
    capabilities: list[str] = Field(default_factory=list)
    endpoint_url: HttpUrl | None = None
    max_parallel_runs: int = Field(default=1, ge=1, le=20)
    timeout_seconds: int = Field(default=900, ge=5, le=86400)
    max_retries: int = Field(default=2, ge=0, le=10)


class RuntimeWorkerRecord(RuntimeWorkerCreate):
    id: UUID = Field(default_factory=uuid4)
    status: RuntimeStatus = RuntimeStatus.idle
    active_runs: int = 0
    last_heartbeat_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RuntimeHeartbeat(BaseModel):
    status: RuntimeStatus = RuntimeStatus.idle


class RuntimeRunCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    payload: dict = Field(default_factory=dict)
    required_capabilities: list[str] = Field(default_factory=list)


class RuntimeRunRecord(RuntimeRunCreate):
    id: UUID = Field(default_factory=uuid4)
    worker_id: UUID | None = None
    status: RunStatus = RunStatus.queued
    attempt: int = 0
    output: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RuntimeRunUpdate(BaseModel):
    status: RunStatus
    output: str | None = None
    error: str | None = None


class RuntimeWorkerList(BaseModel):
    items: list[RuntimeWorkerRecord]
    count: int


class RuntimeRunList(BaseModel):
    items: list[RuntimeRunRecord]
    count: int


class RuntimeSummary(BaseModel):
    workers: int
    idle_workers: int
    busy_workers: int
    queued_runs: int
    running_runs: int
    failed_runs: int
