from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BridgeState(str, Enum):
    draft = "draft"
    awaiting_approval = "awaiting_approval"
    active = "active"
    blocked = "blocked"
    completed = "completed"


class ExecutionLink(BaseModel):
    milestone_id: UUID
    mission_id: UUID
    dependencies: list[UUID] = Field(default_factory=list)
    assigned_agent: str | None = None
    progress: float = Field(default=0, ge=0, le=1)
    blocker: str | None = None


class BridgeCreate(BaseModel):
    plan_id: UUID
    approved_by: str | None = Field(default=None, min_length=1, max_length=120)
    default_token_limit: int = Field(default=100_000, ge=1)
    default_cost_limit_usd: float = Field(default=20, ge=0)
    default_runtime_limit_seconds: int = Field(default=3600, ge=60)
    default_max_retries: int = Field(default=2, ge=0, le=10)
    agent_map: dict[str, str] = Field(default_factory=dict)


class BridgeApproval(BaseModel):
    approved_by: str = Field(min_length=1, max_length=120)


class BridgeRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    plan_id: UUID
    state: BridgeState = BridgeState.awaiting_approval
    approved_by: str | None = None
    links: list[ExecutionLink] = Field(default_factory=list)
    progress: float = Field(default=0, ge=0, le=1)
    blocker: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BridgeListResponse(BaseModel):
    items: list[BridgeRecord]
    count: int


class BridgeStatus(BaseModel):
    total: int
    awaiting_approval: int
    active: int
    blocked: int
    completed: int
    automatic_execution: bool = False
    automatic_order_execution: bool = False
    automatic_merge: bool = False
