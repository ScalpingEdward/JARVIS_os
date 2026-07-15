from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AutoFixStatus(StrEnum):
    active = "active"
    awaiting_patch = "awaiting_patch"
    testing = "testing"
    succeeded = "succeeded"
    escalated = "escalated"


class AutoFixCreate(BaseModel):
    workspace_id: UUID
    max_attempts: int = Field(default=3, ge=1, le=5)


class AutoFixPatch(BaseModel):
    attempt: int = Field(ge=1)
    summary: str = Field(min_length=3, max_length=4000)


class AutoFixRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    max_attempts: int
    attempts: int = 0
    status: AutoFixStatus = AutoFixStatus.active
    last_sandbox_run_id: UUID | None = None
    last_failure: str | None = None
    fix_prompt: str | None = None
    patch_summary: str | None = None
    escalation_reason: str | None = None
    audit_log: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AutoFixList(BaseModel):
    items: list[AutoFixRecord]
    count: int
