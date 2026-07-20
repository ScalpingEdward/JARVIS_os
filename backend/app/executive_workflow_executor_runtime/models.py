from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class WorkflowExecutorState(str, Enum):
    blocked = "blocked"
    waiting_timer = "waiting-timer"
    lease_conflict = "lease-conflict"
    worker_unavailable = "worker-unavailable"
    retry_scheduled = "retry-scheduled"
    recovery_required = "recovery-required"
    task_ready = "task-ready"
    dispatched = "dispatched"


class TaskExecutionObservation(BaseModel):
    task_persisted: bool = False
    queue_registered: bool = False
    worker_registered: bool = False
    worker_capability_match: bool = False
    lease_acquired: bool = False
    lease_owner_verified: bool = False
    lease_expired: bool = False
    heartbeat_verified: bool = False
    timer_persisted: bool = False
    timer_due: bool = True
    retry_checkpoint_persisted: bool = False
    dispatch_acknowledged: bool = False
    result_checkpoint_persisted: bool = False
    graceful_shutdown_verified: bool = False
    raw_worker_credentials_present: bool = False
    attempts: int = Field(default=0, ge=0, le=20)
    lease_age_seconds: int = Field(default=0, ge=0)
    heartbeat_age_seconds: int = Field(default=0, ge=0)
    execution_age_seconds: int = Field(default=0, ge=0)
    retry_delay_seconds: int = Field(default=0, ge=0)
    queue_depth: int = Field(default=0, ge=0)


class WorkflowExecutorPolicy(BaseModel):
    maximum_attempts: int = Field(default=5, ge=1, le=20)
    maximum_lease_age_seconds: int = Field(default=300, ge=1)
    maximum_heartbeat_age_seconds: int = Field(default=60, ge=1)
    maximum_execution_age_seconds: int = Field(default=3600, ge=1)
    maximum_queue_depth: int = Field(default=100000, ge=0)
    maximum_retry_delay_seconds: int = Field(default=3600, ge=0)
    require_task_persistence: bool = True
    require_worker_capability_match: bool = True
    require_lease_and_heartbeat: bool = True
    require_durable_timer: bool = True
    require_dispatch_ack: bool = True
    require_result_checkpoint: bool = True
    allow_expired_lease_recovery: bool = True
    prohibit_raw_worker_credentials: bool = True


class WorkflowExecutorAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    workflow_assessment_id: str = Field(min_length=1, max_length=120)
    workflow_state: str = Field(min_length=1, max_length=40)
    workflow_instance_id: UUID
    task_id: UUID = Field(default_factory=uuid4)
    step_id: str = Field(min_length=1, max_length=120)
    target_module: str = Field(min_length=1, max_length=180)
    worker_id: str = Field(min_length=1, max_length=120)
    queue_name: str = Field(min_length=1, max_length=180)
    observation: TaskExecutionObservation = Field(default_factory=TaskExecutionObservation)
    risk_brain_clear: bool = True
    policy: WorkflowExecutorPolicy = Field(default_factory=WorkflowExecutorPolicy)


class WorkflowExecutorScores(BaseModel):
    task_durability: int = Field(ge=0, le=100)
    worker_readiness: int = Field(ge=0, le=100)
    lease_integrity: int = Field(ge=0, le=100)
    timer_reliability: int = Field(ge=0, le=100)
    recovery_readiness: int = Field(ge=0, le=100)
    executor_confidence: int = Field(ge=0, le=100)


class WorkflowExecutorAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    workflow_instance_id: UUID
    task_id: UUID
    step_id: str
    worker_id: str
    queue_name: str
    state: WorkflowExecutorState
    dispatchable: bool
    recoverable: bool
    target_module: str | None
    recommended_action: str
    scores: WorkflowExecutorScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkflowExecutorStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    dispatched: int
    waiting_or_retrying: int
    recovery_required: int
    latest_state: WorkflowExecutorState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    task_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
