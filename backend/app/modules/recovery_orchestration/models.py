from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class OrchestrationState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    VALIDATED = "validated"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    VERIFIED = "verified"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    BOUNDED_PARALLEL = "bounded-parallel"


class OrchestrationTask(BaseModel):
    task_id: str = Field(min_length=1, max_length=120)
    recovery_step_id: str = Field(min_length=1, max_length=120)
    command_type: str = Field(min_length=1, max_length=120)
    target: str = Field(min_length=1, max_length=240)
    depends_on: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    max_attempts: int = Field(default=1, ge=1, le=10)
    concurrency_key: str | None = Field(default=None, max_length=160)
    required_evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrchestrationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    recovery_plan_id: str = Field(min_length=1, max_length=180)
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    max_parallel_tasks: int = Field(default=1, ge=1, le=20)
    tasks: list[OrchestrationTask] = Field(min_length=1)
    planning_evidence_refs: list[str] = Field(min_length=1)
    runtime_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_orchestration(self) -> "OrchestrationCreate":
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task_id values must be unique")
        known = set(task_ids)
        graph: dict[str, set[str]] = {}
        for task in self.tasks:
            if task.task_id in task.depends_on:
                raise ValueError("orchestration task cannot depend on itself")
            missing = set(task.depends_on) - known
            if missing:
                raise ValueError("all dependencies must reference known orchestration tasks")
            graph[task.task_id] = set(task.depends_on)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("orchestration task dependencies must be acyclic")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)
        if self.execution_mode == ExecutionMode.SEQUENTIAL and self.max_parallel_tasks != 1:
            raise ValueError("sequential execution requires max_parallel_tasks=1")
        return self


class OrchestrationActionRequest(BaseModel):
    action: str = Field(pattern="^(validate|request-review|approve|schedule|start|complete-task|fail-task|pause|resume|verify|cancel|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    task_id: str | None = Field(default=None, max_length=120)
    attempt: int | None = Field(default=None, ge=1, le=10)
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class TaskExecution(BaseModel):
    task_id: str
    attempts: int = 0
    running: bool = False
    completed: bool = False
    failed: bool = False
    receipt_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: OrchestrationState | None = None
    to_state: OrchestrationState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class RecoveryOrchestration(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    recovery_plan_id: str
    execution_mode: ExecutionMode
    max_parallel_tasks: int
    tasks: list[OrchestrationTask]
    planning_evidence_refs: list[str]
    runtime_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: OrchestrationState = OrchestrationState.DRAFT
    execution: dict[str, TaskExecution] = Field(default_factory=dict)
    approval_actor: str | None = None
    verification_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
