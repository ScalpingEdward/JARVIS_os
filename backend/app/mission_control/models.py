from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class AgentRole(str, Enum):
    PLANNER = "planner"
    RESEARCHER = "researcher"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    TESTER = "tester"
    OPERATOR = "operator"


class AgentState(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    DEGRADED = "degraded"


class MissionState(str, Enum):
    DRAFT = "draft"
    PLANNED = "planned"
    APPROVED = "approved"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class TaskState(str, Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    READY = "ready"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentRegistration(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    agent_key: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    role: AgentRole
    capabilities: list[str] = Field(default_factory=list, max_length=100)
    max_concurrent_tasks: int = Field(default=1, ge=1, le=20)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_approval(self) -> "AgentRegistration":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class AgentRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    agent_key: str
    name: str
    role: AgentRole
    capabilities: list[str]
    max_concurrent_tasks: int
    state: AgentState = AgentState.AVAILABLE
    active_task_ids: list[UUID] = Field(default_factory=list)
    last_heartbeat_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MissionTask(BaseModel):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    required_role: AgentRole
    required_capabilities: list[str] = Field(default_factory=list, max_length=50)
    depends_on: list[str] = Field(default_factory=list, max_length=100)
    priority: Priority = Priority.MEDIUM
    requires_human_approval: bool = False
    estimated_tokens: int = Field(default=0, ge=0, le=10_000_000)
    estimated_cost: float = Field(default=0.0, ge=0.0)
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "MissionTask":
        if self.automatic_external_action:
            raise ValueError("automatic external actions are disabled")
        return self


class MissionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    mission_key: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=10000)
    tasks: list[MissionTask] = Field(min_length=1, max_length=500)
    token_budget: int = Field(default=0, ge=0, le=100_000_000)
    cost_budget: float = Field(default=0.0, ge=0.0)
    human_approved: bool = True

    @model_validator(mode="after")
    def validate_definition(self) -> "MissionCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        keys = [task.key for task in self.tasks]
        if len(keys) != len(set(keys)):
            raise ValueError("task keys must be unique")
        known = set(keys)
        for task in self.tasks:
            if task.key in task.depends_on:
                raise ValueError("task cannot depend on itself")
            if not set(task.depends_on).issubset(known):
                raise ValueError("task dependency does not exist")
        if self.token_budget and sum(t.estimated_tokens for t in self.tasks) > self.token_budget:
            raise ValueError("estimated token usage exceeds mission budget")
        if self.cost_budget and sum(t.estimated_cost for t in self.tasks) > self.cost_budget:
            raise ValueError("estimated cost exceeds mission budget")
        return self


class MissionAction(BaseModel):
    actor_id: str = Field(min_length=1, max_length=120)
    human_approved: bool = True
    reason: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def require_approval(self) -> "MissionAction":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class TaskRuntime(BaseModel):
    task_key: str
    state: TaskState = TaskState.PENDING
    assigned_agent_id: UUID | None = None
    attempts: int = 0
    tokens_used: int = 0
    cost_used: float = 0.0
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class MissionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    mission_key: str
    name: str
    objective: str
    state: MissionState = MissionState.DRAFT
    version: int = 1
    tasks: list[MissionTask]
    runtime: list[TaskRuntime]
    token_budget: int
    cost_budget: float
    tokens_used: int = 0
    cost_used: float = 0.0
    approved_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    entity_id: UUID
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MissionControlStatus(BaseModel):
    service: str = "mission-control"
    version: str = "13.0"
    total_agents: int
    available_agents: int
    total_missions: int
    active_missions: int
    autonomous_execution: bool = False
    automatic_external_actions: bool = False
    human_approval_required: bool = True
