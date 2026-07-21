from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ImplementationState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    INPUT_INVALID = "input-invalid"
    IMPLEMENTATION_PENDING = "implementation-pending"
    APPROVAL_REQUIRED = "approval-required"
    READY = "ready"
    APPLYING = "applying"
    TESTING = "testing"
    REVIEW_REQUIRED = "review-required"
    PR_READY = "pr-ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class FileChange(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    operation: str = Field(pattern="^(create|update|delete)$")
    summary: str = Field(min_length=1, max_length=1000)
    protected: bool = False


class ControlledImplementationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    plan_id_v20_01: str = Field(min_length=1, max_length=160)
    plan_approved_v20_01: bool = False
    human_approved: bool = False
    upstream_risk_brain_blocked: bool = False
    base_branch: str = Field(default="main", min_length=1, max_length=160)
    implementation_branch: str = Field(min_length=1, max_length=200)
    base_commit: str = Field(min_length=7, max_length=64)
    objective: str = Field(min_length=1, max_length=2000)
    changes: list[FileChange] = Field(min_length=1, max_length=50)
    required_tests: list[str] = Field(default_factory=list, max_length=50)
    rollback_plan: str = Field(min_length=1, max_length=2000)
    ci_required: bool = True
    diff_review_required: bool = True

    @model_validator(mode="after")
    def validate_boundaries(self):
        if self.base_branch != "main":
            raise ValueError("base_branch must be main")
        if self.implementation_branch == "main":
            raise ValueError("implementation branch must be isolated from main")
        return self


class ImplementationExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(approve|start|mark-tests-passed|mark-review-passed|archive|fail)$")
    human_approved: bool | None = None
    ci_passed: bool | None = None
    diff_review_passed: bool | None = None
    commit_sha: str | None = Field(default=None, min_length=7, max_length=64)
    pull_request_url: str | None = Field(default=None, max_length=500)
    detail: str | None = Field(default=None, max_length=1000)


class ImplementationStep(BaseModel):
    order: int
    name: str
    status: str = "pending"
    evidence: str = ""


class ControlledImplementationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: ImplementationState
    detail: str
    request: ControlledImplementationCreate
    risk_level: str = "standard"
    blocked_reasons: list[str] = Field(default_factory=list)
    steps: list[ImplementationStep] = Field(default_factory=list)
    commit_sha: str | None = None
    pull_request_url: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ControlledImplementationStatus(BaseModel):
    module: str = "executive-controlled-code-implementation"
    version: str = "20.02"
    workspace_id: str
    total_records: int
    active_records: int
    review_records: int
    pr_ready_records: int


class ControlledImplementationAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: ImplementationState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
