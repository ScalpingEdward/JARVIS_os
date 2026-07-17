from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class RunbookState(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    RETIRED = "retired"


class StepKind(str, Enum):
    CHECK = "check"
    MANUAL = "manual"
    DECISION = "decision"
    EVIDENCE = "evidence"
    COMMUNICATION = "communication"


class RunState(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in-progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepState(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class RunbookStep(BaseModel):
    step_key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9_.-]+$")
    title: str = Field(min_length=1, max_length=300)
    instructions: str = Field(min_length=1, max_length=12000)
    kind: StepKind = StepKind.MANUAL
    required_role: str = Field(default="operator", min_length=1, max_length=120)
    required_evidence: bool = False
    optional: bool = False


class RunbookCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    runbook_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=6000)
    service_keys: list[str] = Field(default_factory=list, max_length=500)
    scenario: str = Field(min_length=1, max_length=300)
    steps: list[RunbookStep] = Field(min_length=1, max_length=200)
    required_approvals: int = Field(default=1, ge=1, le=20)
    labels: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_publish: bool = False
    execute_steps: bool = False
    external_runner: bool = False

    @model_validator(mode="after")
    def validate_runbook(self) -> "RunbookCreate":
        keys = [step.step_key for step in self.steps]
        if len(keys) != len(set(keys)):
            raise ValueError("runbook step keys must be unique")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_publish:
            raise ValueError("automatic runbook publication is disabled")
        if self.execute_steps:
            raise ValueError("runbook records never execute operational steps")
        if self.external_runner:
            raise ValueError("external runbook runners are disabled")
        return self


class RunbookRecord(RunbookCreate):
    id: UUID = Field(default_factory=uuid4)
    version: int = 1
    state: RunbookState = RunbookState.DRAFT
    approval_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Mutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=4000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "Mutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class ApprovalCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    runbook_id: UUID
    comment: str = Field(default="", max_length=4000)
    human_approved: bool = True
    automatic_decision: bool = False

    @model_validator(mode="after")
    def safety(self) -> "ApprovalCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_decision:
            raise ValueError("automatic runbook approvals are disabled")
        return self


class ApprovalRecord(ApprovalCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RunCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    runbook_id: UUID
    operator_id: str = Field(min_length=1, max_length=120)
    context_reference: str = Field(default="", max_length=1000)
    dry_run: bool = True
    human_approved: bool = True
    execute_steps: bool = False

    @model_validator(mode="after")
    def safety(self) -> "RunCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_steps:
            raise ValueError("runbook runs are planning and evidence records only")
        return self


class RunRecord(RunCreate):
    id: UUID = Field(default_factory=uuid4)
    runbook_version: int
    state: RunState = RunState.PLANNED
    current_step_index: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StepResultCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    run_id: UUID
    step_key: str = Field(min_length=1, max_length=120)
    state: StepState
    notes: str = Field(default="", max_length=8000)
    evidence_references: list[str] = Field(default_factory=list, max_length=500)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "StepResultCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class StepResultRecord(StepResultCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsRecord(BaseModel):
    workspace_id: str
    runbooks: int
    published_runbooks: int
    active_runs: int
    completed_runs: int
    failed_runs: int
    blocked_runs: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    entity_type: str
    entity_id: UUID | None = None
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RunbookStatus(BaseModel):
    version: str = "10.4"
    runbooks: int
    runs: int
    step_results: int
    automatic_publish_enabled: bool = False
    executes_steps: bool = False
    external_runner_enabled: bool = False
