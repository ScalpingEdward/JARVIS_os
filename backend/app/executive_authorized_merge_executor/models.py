from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class MergeExecutionState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    AUTHORIZATION_PENDING = "authorization-pending"
    READY = "ready"
    MERGE_REQUESTED = "merge-requested"
    MERGED = "merged"
    POST_MERGE_VERIFYING = "post-merge-verifying"
    VERIFIED = "verified"
    ROLLBACK_REQUIRED = "rollback-required"
    FAILED = "failed"
    ARCHIVED = "archived"


class MergeExecutionEvidence(BaseModel):
    pull_request_number: int = Field(gt=0)
    authorized_head_sha: str = Field(min_length=7, max_length=64)
    current_head_sha: str = Field(min_length=7, max_length=64)
    base_branch: str = Field(min_length=1, max_length=120)
    authorization_token: str = Field(min_length=8, max_length=200)
    v20_04_merge_authorized: bool = False
    ci_passed: bool = False
    tests_passed: bool = False
    unresolved_comments: int = Field(ge=0)
    rollback_verified: bool = False
    mergeable: bool = False

    @model_validator(mode="after")
    def validate_commit_binding(self):
        if self.authorized_head_sha != self.current_head_sha:
            raise ValueError("authorized and current head SHA must match")
        return self


class AuthorizedMergeCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    upstream_risk_brain_blocked: bool = False
    human_approved: bool = False
    evidence: MergeExecutionEvidence


class MergeExecutionRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(request-merge|confirm-merged|verify-post-merge|mark-rollback-required|archive)$")
    human_approved: bool | None = None
    merge_commit_sha: str | None = Field(default=None, min_length=7, max_length=64)
    post_merge_ci_passed: bool | None = None
    post_merge_tests_passed: bool | None = None


class AuthorizedMergeRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: MergeExecutionState
    detail: str
    request: AuthorizedMergeCreate
    merge_commit_sha: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuthorizedMergeStatus(BaseModel):
    module: str = "executive-authorized-merge-executor"
    version: str = "20.05"
    workspace_id: str
    total_records: int
    verified_records: int
    rollback_records: int


class AuthorizedMergeAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: MergeExecutionState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
