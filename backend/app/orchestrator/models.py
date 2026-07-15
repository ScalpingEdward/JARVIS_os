from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    queued = "queued"
    assigned = "assigned"
    in_progress = "in_progress"
    blocked = "blocked"
    completed = "completed"
    failed = "failed"


class AgentStatus(StrEnum):
    available = "available"
    busy = "busy"
    offline = "offline"


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    capabilities: list[str] = Field(default_factory=list)


class AgentRecord(AgentCreate):
    id: UUID = Field(default_factory=uuid4)
    status: AgentStatus = AgentStatus.available
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    priority: int = Field(default=50, ge=1, le=100)
    required_capabilities: list[str] = Field(default_factory=list)


class TaskRecord(TaskCreate):
    id: UUID = Field(default_factory=uuid4)
    status: TaskStatus = TaskStatus.queued
    assigned_agent_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskListResponse(BaseModel):
    items: list[TaskRecord]
    count: int


class AgentListResponse(BaseModel):
    items: list[AgentRecord]
    count: int


class OrchestratorStatus(BaseModel):
    queued_tasks: int
    active_tasks: int
    completed_tasks: int
    registered_agents: int
    available_agents: int
