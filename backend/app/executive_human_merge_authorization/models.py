from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class MergeAuthorizationState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    AUTHORIZATION_PENDING = "authorization-pending"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    RELEASE_CANDIDATE = "release-candidate"
    MERGE_AUTHORIZED = "merge-authorized"
    MERGE_REJECTED = "merge-rejected"
    EXPIRED = "expired"
    ARCHIVED = "archived"
    FAILED = "failed"


class MergeEvidence(BaseModel):
    pull_request_number: int = Field(gt=0)
    branch_name: str = Field(min_length=1, max_length=160)
    head_commit_sha: str = Field(min_length=7, max_length=64)
    base_commit_sha: str = Field(min_length=7, max_length=64)
    ci_passed: bool = False
    tests_passed: bool = False
    diff_reviewed: bool = False
    rollback_verified: bool = False
    unresolved_comments: int = Field(default=0, ge=0)
    critical_findings: int = Field(default=0, ge=0)
    protected_paths_changed: bool = False
    risk_or_execution_changed: bool = False
    v20_03_merge_recommended: bool = False

    @model_validator(mode="after")
    def validate_branch(self):
        if self.branch_name in {"main", "master"}:
            raise ValueError("release candidate branch may not be main or master")
        if self.head_commit_sha == self.base_commit_sha:
            raise ValueError("head and base commit must differ")
        return self


class MergeAuthorizationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    upstream_risk_brain_blocked: bool = False
    human_approved: bool = False
    release_notes: str = Field(min_length=1, max_length=2000)
    evidence: MergeEvidence


class MergeAuthorizationExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(confirm-review|authorize-merge|reject-merge|expire|archive)$")
    human_approved: bool | None = None
    confirmation_token: str | None = Field(default=None, min_length=6, max_length=160)


class MergeAuthorizationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: MergeAuthorizationState
    detail: str
    request: MergeAuthorizationCreate
    release_candidate_id: str = ""
    merge_authorized: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MergeAuthorizationStatus(BaseModel):
    module: str = "executive-human-merge-authorization"
    version: str = "20.04"
    workspace_id: str
    total_records: int
    authorized_records: int
    blocked_records: int


class MergeAuthorizationAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: MergeAuthorizationState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
