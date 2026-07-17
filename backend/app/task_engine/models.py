from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class AgentState(str, Enum):
    REGISTERED = "registered"
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class TaskState(str, Enum):
    QUEUED = "queued"
    BLOCKED = "blocked"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class AgentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    agent_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=300)
    capabilities: list[str] = Field(default_factory=list, max_length=200)
    permissions: list[str] = Field(default_factory=list, max_length=200)
    memory_namespace: str = Field(min_length=1, max_length=200)
    max_concurrent_tasks: int = Field(default=1, ge=1, le=100)
    monthly_token_budget: int = Field(default=0, ge=0, le=1_000_000_000)
    cpu_budget_seconds: int = Field(default=0, ge=0, le=10_000_000)
    memory_budget_mb: int = Field(default=512, ge=64, le=1_000_000)
    human_approved: bool = True
    autonomous_external_execution: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "AgentCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.autonomous_external_execution:
            raise ValueError("autonomous external execution is disabled")
        return self


class AgentRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    agent_key: str
    name: str
    role: str
    capabilities: list[str]
    permissions: list[str]
    memory_namespace: str
    max_concurrent_tasks: int
    monthly_token_budget: int
    consumed_tokens: int = 0
    cpu_budget_seconds: int
    consumed_cpu_seconds: int = 0
    memory_budget_mb: int
    state: AgentState = AgentState.REGISTERED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    agent_id: UUID
    task_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20_000)
    priority: TaskPriority = TaskPriority.NORMAL
    dependency_ids: list[UUID] = Field(default_factory=list, max_length=200)
    max_retries: int = Field(default=3, ge=0, le=100)
    token_budget: int = Field(default=0, ge=0, le=100_000_000)
    cpu_budget_seconds: int = Field(default=0, ge=0, le=1_000_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True
    human_approved: bool = True
    execute_external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "TaskCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if not self.dry_run or self.execute_external_action:
            raise ValueError("v8.7 permits supervised dry-run task orchestration only")
        if self.agent_id in self.dependency_ids:
            raise ValueError("task dependencies must contain task ids, not the agent id")
        return self


class TaskRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    agent_id: UUID
    task_key: str
    title: str
    description: str
    priority: TaskPriority
    dependency_ids: list[UUID]
    max_retries: int
    retry_count: int = 0
    token_budget: int
    consumed_tokens: int = 0
    cpu_budget_seconds: int
    consumed_cpu_seconds: int = 0
    progress: float = Field(default=0, ge=0, le=1)
    state: TaskState = TaskState.QUEUED
    checkpoint_id: UUID | None = None
    blocked_reason: str | None = None
    last_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskMutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    human_approved: bool = True
    reason: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def require_approval(self) -> "TaskMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class ProgressUpdate(TaskMutation):
    progress: float = Field(ge=0, le=1)
    consumed_tokens: int = Field(default=0, ge=0)
    consumed_cpu_seconds: int = Field(default=0, ge=0)


class FailureRequest(TaskMutation):
    error: str = Field(min_length=1, max_length=5000)
    retryable: bool = True


class CheckpointCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    task_id: UUID
    requester_id: str = Field(min_length=1, max_length=120)
    sequence: int = Field(ge=0)
    state_data: dict[str, Any] = Field(default_factory=dict)
    note: str = Field(default="", max_length=5000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_approval(self) -> "CheckpointCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class CheckpointRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    task_id: UUID
    requester_id: str
    sequence: int
    state_data: dict[str, Any]
    note: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryWrite(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    agent_id: UUID
    requester_id: str = Field(min_length=1, max_length=120)
    key: str = Field(min_length=1, max_length=300)
    value: Any
    tags: list[str] = Field(default_factory=list, max_length=100)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_approval(self) -> "MemoryWrite":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class MemoryRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    agent_id: UUID
    namespace: str
    key: str
    value: Any
    tags: list[str]
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    task_id: UUID | None = None
    agent_id: UUID | None = None
    event_type: str
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskEngineStatus(BaseModel):
    service: str = "task-engine"
    version: str = "8.7"
    agents: int
    tasks: int
    queued: int
    running: int
    blocked: int
    dead_letter: int
    checkpoints: int
    memory_records: int
    dry_run_only: bool = True
    autonomous_external_execution: bool = False
