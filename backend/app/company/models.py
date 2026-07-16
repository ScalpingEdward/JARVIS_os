from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CompanyRole(str, Enum):
    CEO = "ceo"
    QUANT = "quant"
    TRADING = "trading"
    RESEARCH = "research"
    BACKEND = "backend"
    FRONTEND = "frontend"
    QA = "qa"
    SECURITY = "security"
    BUSINESS = "business"


class AgentState(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    BLOCKED = "blocked"
    REVIEWING = "reviewing"
    PAUSED = "paused"


class WorkStatus(str, Enum):
    PLANNED = "planned"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    REJECTED = "rejected"


class CompanyAgent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    role: CompanyRole
    capabilities: list[str] = Field(default_factory=list)
    state: AgentState = AgentState.IDLE
    active_work_item_id: UUID | None = None


class CompanyAgentList(BaseModel):
    items: list[CompanyAgent]
    count: int


class MissionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    objective: str = Field(min_length=10, max_length=4000)
    priority: int = Field(default=2, ge=1, le=4)
    human_approval_required: bool = True


class MissionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    objective: str
    priority: int
    human_approval_required: bool
    status: WorkStatus = WorkStatus.PLANNED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    title: str
    owner_role: CompanyRole
    reviewer_role: CompanyRole
    depends_on: list[UUID] = Field(default_factory=list)
    status: WorkStatus = WorkStatus.PLANNED
    result_summary: str | None = None
    requires_human_approval: bool = False


class MissionDetail(BaseModel):
    mission: MissionRecord
    work_items: list[WorkItem]
    completion_percent: int
    ready_count: int
    blocked_count: int


class WorkStatusUpdate(BaseModel):
    status: WorkStatus
    result_summary: str | None = Field(default=None, max_length=4000)


class CompanyStatus(BaseModel):
    operating_mode: str = "human_supervised"
    agents: int
    active_missions: int
    active_work_items: int
    blocked_work_items: int
    automatic_merge: bool = False
    automatic_order_execution: bool = False
