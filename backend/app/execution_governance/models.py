from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ReleaseStatus(str, Enum):
    draft = "draft"
    validated = "validated"
    pending_approval = "pending-approval"
    approved = "approved"
    rejected = "rejected"
    blocked = "blocked"


class GateType(str, Enum):
    policy = "policy"
    risk = "risk"
    maintenance_window = "maintenance-window"
    change_freeze = "change-freeze"
    rollback = "rollback"
    dry_run = "dry-run"
    checklist = "checklist"


class GateState(str, Enum):
    passed = "passed"
    failed = "failed"
    warning = "warning"


class ApprovalDecision(str, Enum):
    approve = "approve"
    reject = "reject"


class ApprovalStage(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    required_approvals: int = Field(default=1, ge=1, le=20)
    approver_roles: list[str] = Field(default_factory=list)


class ExecutionGateInput(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    gate_type: GateType
    title: str = Field(min_length=1, max_length=200)
    passed: bool
    evidence: list[str] = Field(default_factory=list)
    blocking: bool = True
    explanation: str = Field(default="", max_length=2000)


class ReleaseCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    target_type: str = Field(min_length=1, max_length=80)
    target_id: str = Field(min_length=1, max_length=160)
    source_orchestration_ids: list[UUID] = Field(default_factory=list)
    requested_window_start: datetime | None = None
    requested_window_end: datetime | None = None
    change_freeze_active: bool = False
    emergency_stop_ready: bool = False
    rollback_steps: list[str] = Field(default_factory=list)
    dry_run_completed: bool = False
    checklist_items: list[str] = Field(default_factory=list)
    completed_checklist_items: list[str] = Field(default_factory=list)
    gates: list[ExecutionGateInput] = Field(default_factory=list)
    approval_stages: list[ApprovalStage] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_release(self):
        if self.requested_window_start and self.requested_window_end and self.requested_window_end <= self.requested_window_start:
            raise ValueError("Execution window end must be after start")
        gate_keys = [gate.key for gate in self.gates]
        if len(gate_keys) != len(set(gate_keys)):
            raise ValueError("Gate keys must be unique")
        stage_keys = [stage.key for stage in self.approval_stages]
        if len(stage_keys) != len(set(stage_keys)):
            raise ValueError("Approval stage keys must be unique")
        return self


class GateResult(BaseModel):
    key: str
    gate_type: GateType
    state: GateState
    blocking: bool
    explanation: str
    evidence: list[str]


class ApprovalRecord(BaseModel):
    stage_key: str
    reviewer_id: str
    reviewer_role: str
    decision: ApprovalDecision
    reason: str
    created_at: datetime


class ReleaseValidation(BaseModel):
    validated_at: datetime
    gate_results: list[GateResult]
    readiness_score: float
    blocking_reasons: list[str]
    warnings: list[str]
    rollback_ready: bool
    dry_run_ready: bool
    checklist_complete: bool
    emergency_stop_ready: bool
    requires_human_approval: bool = True
    autonomous_execution_enabled: bool = False


class ExecutionRelease(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    title: str
    target_type: str
    target_id: str
    source_orchestration_ids: list[UUID]
    requested_window_start: datetime | None
    requested_window_end: datetime | None
    change_freeze_active: bool
    emergency_stop_ready: bool
    rollback_steps: list[str]
    dry_run_completed: bool
    checklist_items: list[str]
    completed_checklist_items: list[str]
    gates: list[ExecutionGateInput]
    approval_stages: list[ApprovalStage]
    status: ReleaseStatus = ReleaseStatus.draft
    validation: ReleaseValidation | None = None
    approvals: list[ApprovalRecord] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ApprovalRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    reviewer_id: str = Field(min_length=1, max_length=100)
    reviewer_role: str = Field(min_length=1, max_length=100)
    stage_key: str = Field(min_length=1, max_length=80)
    decision: ApprovalDecision
    reason: str = Field(min_length=3, max_length=1000)


class GovernanceStatus(BaseModel):
    version: str = "17.2"
    releases: int
    pending_approval: int
    approved: int
    blocked: int
    autonomous_execution_enabled: bool = False


class ReleaseListResponse(BaseModel):
    items: list[ExecutionRelease]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    release_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
