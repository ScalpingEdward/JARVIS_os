from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class WorkflowState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class NodeType(str, Enum):
    START = "start"
    AGENT_TASK = "agent_task"
    CONDITION = "condition"
    HUMAN_APPROVAL = "human_approval"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    END = "end"


class RunState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeRunState(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class WorkflowNode(BaseModel):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    node_type: NodeType
    name: str = Field(min_length=1, max_length=200)
    required_capability: str | None = Field(default=None, max_length=120)
    config: dict[str, Any] = Field(default_factory=dict)
    requires_human_approval: bool = False
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def enforce_node_safety(self) -> "WorkflowNode":
        if self.automatic_external_action:
            raise ValueError("automatic external actions are disabled")
        if self.node_type == NodeType.AGENT_TASK and not self.required_capability:
            raise ValueError("agent_task nodes require a capability")
        if self.node_type == NodeType.HUMAN_APPROVAL:
            self.requires_human_approval = True
        return self


class WorkflowEdge(BaseModel):
    source: str = Field(min_length=1, max_length=120)
    target: str = Field(min_length=1, max_length=120)
    condition_key: str | None = Field(default=None, max_length=120)
    condition_value: str | bool | int | float | None = None


class WorkflowCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    nodes: list[WorkflowNode] = Field(min_length=2, max_length=200)
    edges: list[WorkflowEdge] = Field(default_factory=list, max_length=1000)
    human_approved: bool = True
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "WorkflowCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_external_action:
            raise ValueError("automatic external actions are disabled")
        return self


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    nodes: list[WorkflowNode] | None = Field(default=None, min_length=2, max_length=200)
    edges: list[WorkflowEdge] | None = Field(default=None, max_length=1000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_approval(self) -> "WorkflowUpdate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class WorkflowRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    name: str
    description: str
    version: int = 1
    state: WorkflowState = WorkflowState.DRAFT
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    validation_errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkflowValidation(BaseModel):
    valid: bool
    errors: list[str]
    start_node: str | None = None
    end_nodes: list[str] = Field(default_factory=list)
    topological_order: list[str] = Field(default_factory=list)


class WorkflowActivation(BaseModel):
    human_approved: bool = True

    @model_validator(mode="after")
    def require_approval(self) -> "WorkflowActivation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class WorkflowRunCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    input_data: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def enforce_run_safety(self) -> "WorkflowRunCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_external_action:
            raise ValueError("automatic external actions are disabled")
        return self


class NodeRunRecord(BaseModel):
    node_key: str
    state: NodeRunState = NodeRunState.PENDING
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class WorkflowRunRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID
    workflow_version: int
    workspace_id: str
    requester_id: str
    state: RunState = RunState.PENDING
    input_data: dict[str, Any]
    context: dict[str, Any] = Field(default_factory=dict)
    nodes: list[NodeRunRecord]
    current_node_keys: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NodeCompletion(BaseModel):
    success: bool
    result: dict[str, Any] = Field(default_factory=dict)
    error: str = Field(default="", max_length=5000)


class NodeApproval(BaseModel):
    approved: bool
    approved_by: str = Field(min_length=1, max_length=120)


class WorkflowDesignerStatus(BaseModel):
    service: str = "workflow-designer"
    version: str = "7.8"
    total_workflows: int
    active_workflows: int
    total_runs: int
    running_runs: int
    waiting_approval_runs: int
    graph_validation_enabled: bool = True
    workflow_versioning_enabled: bool = True
    automatic_external_actions: bool = False
