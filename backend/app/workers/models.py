from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class WorkerType(StrEnum):
    mock = "mock"
    webhook = "webhook"
    codex = "codex"
    claude = "claude"
    cursor = "cursor"


class DispatchStatus(StrEnum):
    accepted = "accepted"
    running = "running"
    completed = "completed"
    failed = "failed"


class WorkerEndpointCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    worker_type: WorkerType
    endpoint_url: HttpUrl | None = None
    capabilities: list[str] = Field(default_factory=list)
    enabled: bool = True


class WorkerEndpointRecord(WorkerEndpointCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DispatchRequest(BaseModel):
    task_id: UUID
    worker_id: UUID


class DispatchRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    worker_id: UUID
    status: DispatchStatus = DispatchStatus.accepted
    external_run_id: str | None = None
    output: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkerCallback(BaseModel):
    status: DispatchStatus
    external_run_id: str | None = None
    output: str | None = None
    error: str | None = None


class WorkerListResponse(BaseModel):
    items: list[WorkerEndpointRecord]
    count: int


class DispatchListResponse(BaseModel):
    items: list[DispatchRecord]
    count: int
