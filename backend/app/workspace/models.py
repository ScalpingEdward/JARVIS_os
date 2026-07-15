from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class WorkspaceStatus(StrEnum):
    planned = "planned"
    approved = "approved"
    running = "running"
    testing = "testing"
    ready_for_pr = "ready_for_pr"
    ci_pending = "ci_pending"
    review_pending = "review_pending"
    completed = "completed"
    failed = "failed"
    blocked = "blocked"


class FileOperation(StrEnum):
    create = "create"
    update = "update"
    delete = "delete"


class WorkspaceFileChange(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    operation: FileOperation
    content: str | None = Field(default=None, max_length=200000)
    expected_sha: str | None = None


class WorkspaceCreate(BaseModel):
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    objective: str = Field(min_length=5, max_length=5000)
    base_branch: str = Field(default="main", min_length=1, max_length=200)
    branch_name: str = Field(min_length=3, max_length=200)
    test_command: str = Field(default="pytest -q", min_length=1, max_length=500)
    require_human_approval: bool = True
    require_green_ci: bool = True


class WorkspacePatch(BaseModel):
    changes: list[WorkspaceFileChange] = Field(min_length=1, max_length=100)
    commit_message: str = Field(min_length=3, max_length=200)
    pull_request_title: str = Field(min_length=3, max_length=200)
    pull_request_body: str = Field(default="", max_length=20000)


class WorkspaceRecord(WorkspaceCreate):
    id: UUID = Field(default_factory=uuid4)
    status: WorkspaceStatus = WorkspaceStatus.planned
    approved: bool = False
    patch: WorkspacePatch | None = None
    branch_created: bool = False
    commit_sha: str | None = None
    pull_request_number: int | None = None
    pull_request_url: str | None = None
    tests_passed: bool | None = None
    ci_passed: bool | None = None
    reviewer_approved: bool | None = None
    error: str | None = None
    audit_log: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkspaceList(BaseModel):
    items: list[WorkspaceRecord]
    count: int


class WorkspaceDecision(BaseModel):
    approved: bool
    reason: str = Field(default="", max_length=2000)


class WorkspaceResult(BaseModel):
    success: bool
    message: str
    workspace: WorkspaceRecord
