from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class SelfExtensionState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    ANALYSIS_PENDING = "analysis-pending"
    PLAN_READY = "plan-ready"
    APPROVAL_REQUIRED = "approval-required"
    APPROVED = "approved"
    IMPLEMENTATION_READY = "implementation-ready"
    ARCHIVED = "archived"
    FAILED = "failed"


class CodeChangeRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    objective: str = Field(min_length=8, max_length=2000)
    target_module: str = Field(min_length=1, max_length=200)
    requested_changes: list[str] = Field(min_length=1, max_length=50)
    protected_paths: list[str] = Field(default_factory=list, max_length=100)
    tests_required: bool = True
    rollback_required: bool = True
    human_approved: bool = False
    upstream_risk_brain_blocked: bool = False
    jarvis_core_approved_v20_00: bool = False

    @model_validator(mode="after")
    def validate_request(self):
        lowered = " ".join(self.requested_changes).lower()
        forbidden = ("bypass", "disable risk", "remove approval", "force live", "relax all limits")
        if any(term in lowered for term in forbidden):
            raise ValueError("unsafe self-extension request")
        return self


class ChangePlanStep(BaseModel):
    order: int
    action: str
    target: str
    validation: str


class CodeChangePlan(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: SelfExtensionState
    detail: str
    request: CodeChangeRequest
    branch_name: str
    steps: list[ChangePlanStep] = Field(default_factory=list)
    risk_level: str = "medium"
    required_checks: list[str] = Field(default_factory=list)
    rollback_plan: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CodeChangeExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(approve|mark-implementation-ready|archive)$")
    human_approved: bool | None = None


class SelfExtensionStatus(BaseModel):
    module: str = "executive-governed-self-extension"
    version: str = "20.01"
    workspace_id: str
    total_plans: int
    approved_plans: int
    blocked_plans: int


class SelfExtensionAudit(BaseModel):
    plan_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: SelfExtensionState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
