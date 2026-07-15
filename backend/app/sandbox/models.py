from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SandboxStatus(StrEnum):
    queued = "queued"
    running = "running"
    passed = "passed"
    failed = "failed"
    timed_out = "timed_out"
    cancelled = "cancelled"


class SandboxRunCreate(BaseModel):
    workspace_id: UUID
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    ref: str = Field(min_length=1, max_length=200)
    test_command: str = Field(min_length=1, max_length=500)
    image: str = Field(default="python:3.12-slim", min_length=1, max_length=200)
    timeout_seconds: int = Field(default=900, ge=10, le=7200)
    cpu_limit: float = Field(default=1.0, ge=0.25, le=8.0)
    memory_mb: int = Field(default=1024, ge=128, le=16384)
    network_enabled: bool = False


class SandboxResultIn(BaseModel):
    exit_code: int | None = None
    stdout: str = Field(default="", max_length=200000)
    stderr: str = Field(default="", max_length=200000)
    timed_out: bool = False


class SandboxRunRecord(SandboxRunCreate):
    id: UUID = Field(default_factory=uuid4)
    status: SandboxStatus = SandboxStatus.queued
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    failure_summary: str | None = None
    fix_prompt: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None


class SandboxRunList(BaseModel):
    items: list[SandboxRunRecord]
    count: int
