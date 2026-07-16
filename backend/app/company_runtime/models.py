from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RuntimeStatus(str, Enum):
    queued = "queued"
    assigned = "assigned"
    working = "working"
    waiting_review = "waiting_review"
    waiting_approval = "waiting_approval"
    blocked = "blocked"
    completed = "completed"
    failed = "failed"
    dead_letter = "dead_letter"
    paused = "paused"


class RuntimeMissionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=4000)
    priority: int = Field(default=3, ge=1, le=5)
    token_limit: int = Field(default=100_000, ge=1)
    cost_limit_usd: float = Field(default=20.0, ge=0)
    runtime_limit_seconds: int = Field(default=3600, ge=60)
    max_retries: int = Field(default=2, ge=0, le=10)


class RuntimeMission(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    objective: str
    priority: int
    status: RuntimeStatus = RuntimeStatus.queued
    token_limit: int
    tokens_used: int = 0
    cost_limit_usd: float
    cost_used_usd: float = 0
    runtime_limit_seconds: int
    max_retries: int
    retry_count: int = 0
    requires_qa: bool = True
    requires_security: bool = True
    requires_human_approval: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RuntimeUpdate(BaseModel):
    status: RuntimeStatus
    tokens_used_delta: int = Field(default=0, ge=0)
    cost_used_delta_usd: float = Field(default=0, ge=0)
    note: str | None = Field(default=None, max_length=2000)


class AuditEntry(BaseModel):
    mission_id: UUID
    action: str
    note: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RuntimeReport(BaseModel):
    queued: int
    active: int
    waiting_review: int
    waiting_approval: int
    completed: int
    failed: int
    dead_letter: int
    total_cost_usd: float
    total_tokens: int
    automatic_merge: bool = False
    automatic_order_execution: bool = False
