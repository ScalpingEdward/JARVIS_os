from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PlaybookState(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    RETIRED = "retired"


class TriggerType(str, Enum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    EVENT = "event"
    WEBHOOK = "webhook"


class StepType(str, Enum):
    CHECK = "check"
    CONDITION = "condition"
    HUMAN_APPROVAL = "human_approval"
    NOTE = "note"
    WORKFLOW_REFERENCE = "workflow_reference"
    ROLLBACK_PLAN = "rollback_plan"


class ExecutionState(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepState(str, Enum):
    PENDING = "pending"
    SIMULATED = "simulated"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TriggerDefinition(BaseModel):
    trigger_type: TriggerType = TriggerType.MANUAL
    schedule: str | None = Field(default=None, max_length=200)
    event_key: str | None = Field(default=None, max_length=200)
    webhook_key: str | None = Field(default=None, max_length=200)
    enabled: bool = False

    @model_validator(mode="after")
    def validate_trigger(self) -> "TriggerDefinition":
        if self.trigger_type == TriggerType.SCHEDULE and not self.schedule:
            raise ValueError("scheduled triggers require a schedule")
        if self.trigger_type == TriggerType.EVENT and not self.event_key:
            raise ValueError("event triggers require an event key")
        if self.trigger_type == TriggerType.WEBHOOK and not self.webhook_key:
            raise ValueError("webhook triggers require a webhook key")
        return self


class PlaybookStep(BaseModel):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    step_type: StepType
    description: str = Field(default="", max_length=5000)
    workflow_id: UUID | None = None
    condition: dict[str, Any] = Field(default_factory=dict)
    retry_limit: int = Field(default=0, ge=0, le=10)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    requires_human_approval: bool = False
    external_execution: bool = False

    @model_validator(mode="after")
    def enforce_step_safety(self) -> "PlaybookStep":
        if self.external_execution:
            raise ValueError("external execution is disabled")
        if self.step_type == StepType.HUMAN_APPROVAL:
            self.requires_human_approval = True
        if self.step_type == StepType.WORKFLOW_REFERENCE and self.workflow_id is None:
            raise ValueError("workflow_reference steps require workflow_id")
        return self


class PlaybookCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    triggers: list[TriggerDefinition] = Field(default_factory=lambda: [TriggerDefinition()])
    steps: list[PlaybookStep] = Field(min_length=1, max_length=200)
    required_approvals: int = Field(default=1, ge=1, le=10)
    external_execution: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "PlaybookCreate":
        if self.external_execution:
            raise ValueError("external execution is disabled")
        if len({step.key for step in self.steps}) != len(self.steps):
            raise ValueError("step keys must be unique")
        return self


class PlaybookRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    key: str
    name: str
    description: str
    version: int = 1
    state: PlaybookState = PlaybookState.DRAFT
    triggers: list[TriggerDefinition]
    steps: list[PlaybookStep]
    required_approvals: int
    reviewers: list[str] = Field(default_factory=list)
    approved_by: list[str] = Field(default_factory=list)
    published_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ActorAction(BaseModel):
    actor_id: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=5000)


class DryRunCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    input_data: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    external_execution: bool = False

    @model_validator(mode="after")
    def enforce_dry_run(self) -> "DryRunCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.external_execution:
            raise ValueError("external execution is disabled")
        return self


class StepSimulation(BaseModel):
    step_key: str
    state: StepState
    message: str


class DryRunRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    playbook_id: UUID
    playbook_version: int
    workspace_id: str
    requester_id: str
    state: ExecutionState = ExecutionState.PLANNED
    input_data: dict[str, Any]
    steps: list[StepSimulation]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


class PlaybookMetrics(BaseModel):
    workspace_id: str
    total_playbooks: int
    published_playbooks: int
    total_dry_runs: int
    waiting_approval_steps: int


class PlaybookEngineStatus(BaseModel):
    service: str = "playbook-engine"
    version: str = "12.0"
    dry_run_only: bool = True
    external_execution_enabled: bool = False
    autonomous_execution_enabled: bool = False
    human_approval_required: bool = True
