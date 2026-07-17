from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class AgentState(str, Enum):
    ONLINE = "online"
    BUSY = "busy"
    OFFLINE = "offline"
    DEGRADED = "degraded"


class TaskState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    LOW = 10
    NORMAL = 50
    HIGH = 80
    CRITICAL = 100


class AgentRegister(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(default="1.0", min_length=1, max_length=40)
    capabilities: list[str] = Field(min_length=1, max_length=50)
    max_concurrent_tasks: int = Field(default=1, ge=1, le=100)
    enabled: bool = True


class AgentRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    version: str
    capabilities: list[str]
    max_concurrent_tasks: int
    enabled: bool
    state: AgentState = AgentState.ONLINE
    current_task_ids: list[UUID] = Field(default_factory=list)
    completed_tasks: int = 0
    failed_tasks: int = 0
    last_heartbeat_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    required_capability: str = Field(min_length=1, max_length=120)
    priority: TaskPriority = TaskPriority.NORMAL
    depends_on: list[UUID] = Field(default_factory=list, max_length=100)
    max_retries: int = Field(default=2, ge=0, le=20)
    requires_human_approval: bool = True
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "TaskCreate":
        if self.automatic_external_action:
            raise ValueError("automatic external actions are disabled")
        return self


class TaskRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str
    required_capability: str
    priority: TaskPriority
    depends_on: list[UUID]
    max_retries: int
    retry_count: int = 0
    state: TaskState = TaskState.QUEUED
    assigned_agent_id: UUID | None = None
    result: str | None = None
    error: str | None = None
    requires_human_approval: bool = True
    human_approved: bool = False
    automatic_external_action: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskComplete(BaseModel):
    success: bool
    result: str = Field(default="", max_length=20000)
    error: str = Field(default="", max_length=5000)


class TaskApproval(BaseModel):
    approved: bool
    approved_by: str = Field(min_length=1, max_length=120)


class OrchestratorStatus(BaseModel):
    service: str = "agent-orchestrator"
    version: str = "7.6"
    registered_agents: int
    queued_tasks: int
    running_tasks: int
    waiting_tasks: int
    failed_tasks: int
    completed_tasks: int
    automatic_external_actions: bool = False
    human_approval_supported: bool = True
