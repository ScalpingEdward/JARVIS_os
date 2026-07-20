from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class WorkflowState(str, Enum):
    blocked = "blocked"
    waiting = "waiting"
    running = "running"
    paused = "paused"
    retrying = "retrying"
    compensating = "compensating"
    rolled_back = "rolled-back"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class StepState(str, Enum):
    pending = "pending"
    ready = "ready"
    running = "running"
    waiting_approval = "waiting-approval"
    succeeded = "succeeded"
    retrying = "retrying"
    failed = "failed"
    compensating = "compensating"
    compensated = "compensated"
    skipped = "skipped"
    cancelled = "cancelled"


class StepKind(str, Enum):
    task = "task"
    condition = "condition"
    approval = "approval"
    parallel = "parallel"
    join = "join"


class WorkflowStepDefinition(BaseModel):
    step_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=180)
    module: str = Field(min_length=1, max_length=180)
    kind: StepKind = StepKind.task
    depends_on: list[str] = Field(default_factory=list)
    condition_key: str | None = Field(default=None, max_length=180)
    condition_expected: str | None = Field(default=None, max_length=180)
    timeout_seconds: int = Field(default=300, ge=1, le=86_400)
    maximum_attempts: int = Field(default=3, ge=1, le=20)
    requires_human_approval: bool = False
    compensation_module: str | None = Field(default=None, max_length=180)
    compensation_required: bool = False


class WorkflowDefinition(BaseModel):
    workflow_key: str = Field(min_length=1, max_length=180)
    version: int = Field(default=1, ge=1, le=10_000)
    name: str = Field(min_length=1, max_length=180)
    steps: list[WorkflowStepDefinition] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_graph(self) -> "WorkflowDefinition":
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Workflow step IDs must be unique")
        known = set(ids)
        for step in self.steps:
            if step.step_id in step.depends_on:
                raise ValueError("Workflow step cannot depend on itself")
            missing = set(step.depends_on) - known
            if missing:
                raise ValueError(f"Workflow dependency does not exist: {sorted(missing)[0]}")
        adjacency = {step.step_id: step.depends_on for step in self.steps}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("Workflow graph must be acyclic")
            if node in visited:
                return
            visiting.add(node)
            for dependency in adjacency[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for node in adjacency:
            visit(node)
        return self


class WorkflowStepObservation(BaseModel):
    step_id: str = Field(min_length=1, max_length=120)
    state: StepState = StepState.pending
    attempts: int = Field(default=0, ge=0, le=20)
    elapsed_seconds: int = Field(default=0, ge=0)
    approval_granted: bool = False
    output_persisted: bool = False
    checkpoint_persisted: bool = False
    compensation_completed: bool = False
    error_code: str | None = Field(default=None, max_length=120)


class WorkflowExecutionObservation(BaseModel):
    definition_validated: bool = True
    graph_acyclic: bool = True
    context_persisted: bool = False
    workflow_checkpoint_persisted: bool = False
    cancellation_requested: bool = False
    pause_requested: bool = False
    resume_requested: bool = False
    compensation_requested: bool = False
    rollback_chain_verified: bool = False
    steps: list[WorkflowStepObservation] = Field(default_factory=list)


class WorkflowOrchestratorPolicy(BaseModel):
    maximum_steps: int = Field(default=100, ge=1, le=200)
    maximum_parallel_steps: int = Field(default=10, ge=1, le=100)
    maximum_workflow_attempts: int = Field(default=5, ge=1, le=20)
    require_persisted_context: bool = True
    require_step_checkpoints: bool = True
    require_workflow_checkpoint: bool = True
    require_human_approval_for_approval_steps: bool = True
    require_compensation_for_completed_mutations: bool = True
    allow_pause_resume: bool = True
    allow_cancellation: bool = True
    allow_compensation: bool = True


class WorkflowAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    sql_outbox_runtime_assessment_id: str = Field(min_length=1, max_length=120)
    sql_outbox_runtime_state: str = Field(min_length=1, max_length=40)
    workflow_instance_id: UUID = Field(default_factory=uuid4)
    definition: WorkflowDefinition
    execution_context: dict[str, Any] = Field(default_factory=dict)
    observation: WorkflowExecutionObservation = Field(default_factory=WorkflowExecutionObservation)
    risk_brain_clear: bool = True
    policy: WorkflowOrchestratorPolicy = Field(default_factory=WorkflowOrchestratorPolicy)


class WorkflowScores(BaseModel):
    graph_integrity: int = Field(ge=0, le=100)
    step_readiness: int = Field(ge=0, le=100)
    checkpoint_quality: int = Field(ge=0, le=100)
    approval_safety: int = Field(ge=0, le=100)
    compensation_readiness: int = Field(ge=0, le=100)
    orchestration_confidence: int = Field(ge=0, le=100)


class WorkflowAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    workflow_instance_id: UUID
    workflow_key: str
    workflow_version: int
    state: WorkflowState
    dispatchable: bool
    executable_step_ids: list[str]
    blocked_step_ids: list[str]
    compensation_step_ids: list[str]
    recommended_action: str
    scores: WorkflowScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkflowStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    running: int
    completed: int
    failed_or_rolled_back: int
    latest_state: WorkflowState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    workflow_instance_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
