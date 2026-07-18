from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class BackupKind(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    SNAPSHOT = "snapshot"
    CONFIGURATION = "configuration"
    EXPORT = "export"


class PolicyState(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class PlanState(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    RETIRED = "retired"


class ExerciseState(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in-progress"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Mutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=4000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "Mutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class BackupPolicyCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    policy_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=300)
    backup_kind: BackupKind
    source_asset_ids: list[UUID] = Field(min_length=1, max_length=200)
    storage_asset_id: UUID
    schedule_expression: str = Field(min_length=1, max_length=500)
    retention_days: int = Field(ge=1, le=3650)
    rpo_minutes: int = Field(ge=1, le=525600)
    rto_minutes: int = Field(ge=1, le=525600)
    encryption_required: bool = True
    verification_required: bool = True
    required_approvals: int = Field(default=1, ge=1, le=20)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    execute_backup: bool = False
    external_provider: bool = False

    @model_validator(mode="after")
    def safety(self) -> "BackupPolicyCreate":
        if len(self.source_asset_ids) != len(set(self.source_asset_ids)):
            raise ValueError("source assets must be unique")
        if self.storage_asset_id in self.source_asset_ids:
            raise ValueError("storage asset cannot be a source asset")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_backup:
            raise ValueError("backup policies never execute backups")
        if self.external_provider:
            raise ValueError("external backup providers are disabled")
        return self


class BackupPolicyRecord(BackupPolicyCreate):
    id: UUID = Field(default_factory=uuid4)
    state: PolicyState = PolicyState.DRAFT
    approval_count: int = 0
    revision: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PolicyApprovalCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    policy_id: UUID
    comment: str = Field(default="", max_length=4000)
    human_approved: bool = True
    automatic_decision: bool = False

    @model_validator(mode="after")
    def safety(self) -> "PolicyApprovalCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_decision:
            raise ValueError("automatic approval decisions are disabled")
        return self


class PolicyApprovalRecord(PolicyApprovalCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RecoveryStep(BaseModel):
    order: int = Field(ge=1, le=1000)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=6000)
    responsible_role: str = Field(min_length=1, max_length=200)
    evidence_required: bool = True


class RecoveryPlanCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    plan_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=300)
    covered_asset_ids: list[UUID] = Field(min_length=1, max_length=200)
    policy_ids: list[UUID] = Field(default_factory=list, max_length=200)
    steps: list[RecoveryStep] = Field(min_length=1, max_length=1000)
    activation_criteria: str = Field(min_length=1, max_length=6000)
    communication_reference: str = Field(default="", max_length=1000)
    runbook_reference: str = Field(default="", max_length=1000)
    required_approvals: int = Field(default=1, ge=1, le=20)
    human_approved: bool = True
    execute_restore: bool = False

    @model_validator(mode="after")
    def safety(self) -> "RecoveryPlanCreate":
        orders = [step.order for step in self.steps]
        if len(orders) != len(set(orders)):
            raise ValueError("recovery step order must be unique")
        if len(self.covered_asset_ids) != len(set(self.covered_asset_ids)):
            raise ValueError("covered assets must be unique")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_restore:
            raise ValueError("recovery plans never execute restores")
        return self


class RecoveryPlanRecord(RecoveryPlanCreate):
    id: UUID = Field(default_factory=uuid4)
    state: PlanState = PlanState.DRAFT
    approval_count: int = 0
    revision: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExerciseCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    recovery_plan_id: UUID
    scheduled_at: datetime
    scenario: str = Field(min_length=1, max_length=6000)
    dry_run: bool = True
    human_approved: bool = True
    execute_restore: bool = False

    @model_validator(mode="after")
    def safety(self) -> "ExerciseCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_restore:
            raise ValueError("recovery exercises never execute restores")
        return self


class ExerciseRecord(ExerciseCreate):
    id: UUID = Field(default_factory=uuid4)
    state: ExerciseState = ExerciseState.PLANNED
    achieved_rpo_minutes: int | None = None
    achieved_rto_minutes: int | None = None
    evidence_references: list[str] = Field(default_factory=list)
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExerciseResult(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    passed: bool
    achieved_rpo_minutes: int = Field(ge=0, le=525600)
    achieved_rto_minutes: int = Field(ge=0, le=525600)
    evidence_references: list[str] = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=6000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "ExerciseResult":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class MetricsRecord(BaseModel):
    workspace_id: str
    policies: int
    active_policies: int
    recovery_plans: int
    published_plans: int
    exercises: int
    passed_exercises: int
    failed_exercises: int


class BackupRecoveryStatus(BaseModel):
    version: str = "11.0"
    backup_execution: bool = False
    restore_execution: bool = False
    external_providers: bool = False
    automatic_failover: bool = False
    human_approval_required: bool = True
