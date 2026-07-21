from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CodeReviewState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    REVIEW_PENDING = "review-pending"
    CHANGES_REQUIRED = "changes-required"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    MERGE_RECOMMENDED = "merge-recommended"
    MERGE_NOT_RECOMMENDED = "merge-not-recommended"
    ARCHIVED = "archived"
    FAILED = "failed"


class ReviewEvidence(BaseModel):
    implementation_id: str = Field(min_length=1, max_length=120)
    branch_name: str = Field(min_length=1, max_length=160)
    base_commit: str = Field(min_length=7, max_length=64)
    head_commit: str = Field(min_length=7, max_length=64)
    draft_pr_url: str = Field(min_length=8, max_length=500)
    changed_files: list[str] = Field(min_length=1, max_length=200)
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)
    tests_added: int = Field(ge=0)
    tests_passed: int = Field(ge=0)
    tests_failed: int = Field(ge=0)
    coverage_pct: float = Field(ge=0, le=100)
    ci_passed: bool = False
    diff_reviewed: bool = False
    rollback_verified: bool = False
    protected_paths_changed: bool = False
    risk_or_execution_changed: bool = False
    security_findings: list[str] = Field(default_factory=list, max_length=100)
    regression_findings: list[str] = Field(default_factory=list, max_length=100)


class AutonomousCodeReviewCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    objective: str = Field(min_length=3, max_length=1000)
    v20_02_pr_ready: bool = False
    upstream_risk_brain_blocked: bool = False
    evidence: ReviewEvidence


class CodeReviewExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(confirm-human-review|recommend-merge|reject-merge|archive)$")
    human_approved: bool | None = None


class ReviewFinding(BaseModel):
    category: str
    severity: str
    detail: str


class AutonomousCodeReviewRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: CodeReviewState
    detail: str
    request: AutonomousCodeReviewCreate
    quality_score: float = 0
    risk_score: float = 0
    findings: list[ReviewFinding] = Field(default_factory=list)
    recommendation: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AutonomousCodeReviewStatus(BaseModel):
    module: str = "executive-autonomous-code-review"
    version: str = "20.03"
    workspace_id: str
    total_records: int
    recommended_records: int
    blocked_records: int


class AutonomousCodeReviewAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: CodeReviewState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
