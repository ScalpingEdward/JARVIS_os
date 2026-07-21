from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class DeploymentState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    PLAN_PENDING = "plan-pending"
    APPROVAL_REQUIRED = "approval-required"
    READY = "ready"
    DEPLOYING = "deploying"
    RUNTIME_VERIFYING = "runtime-verifying"
    HEALTHY = "healthy"
    ROLLBACK_REQUIRED = "rollback-required"
    ROLLING_BACK = "rolling-back"
    ROLLED_BACK = "rolled-back"
    FAILED = "failed"
    ARCHIVED = "archived"


class DeploymentEvidence(BaseModel):
    merge_commit_sha: str = Field(min_length=7, max_length=64)
    environment: str = Field(pattern="^(staging|production)$")
    artifact_digest: str = Field(min_length=8, max_length=160)
    v20_05_verified: bool = False
    pre_deploy_ci_passed: bool = False
    tests_passed: bool = False
    secrets_validated: bool = False
    migrations_validated: bool = False
    rollback_verified: bool = False
    runtime_health_passed: bool = False
    smoke_tests_passed: bool = False
    error_rate_pct: float = Field(default=0, ge=0, le=100)
    p95_latency_ms: float = Field(default=0, ge=0)


class ControlledDeploymentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    service_name: str = Field(min_length=1, max_length=160)
    release_version: str = Field(min_length=1, max_length=80)
    evidence: DeploymentEvidence
    upstream_risk_brain_blocked: bool = False
    human_approved: bool = False
    max_error_rate_pct: float = Field(default=2.0, ge=0, le=100)
    max_p95_latency_ms: float = Field(default=1500, gt=0)


class DeploymentExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(approve|start-deployment|verify-runtime|start-rollback|complete-rollback|archive)$")
    human_approved: bool | None = None
    runtime_health_passed: bool | None = None
    smoke_tests_passed: bool | None = None
    error_rate_pct: float | None = Field(default=None, ge=0, le=100)
    p95_latency_ms: float | None = Field(default=None, ge=0)


class DeploymentStep(BaseModel):
    name: str
    required: bool = True
    status: str = "pending"


class ControlledDeploymentRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: DeploymentState
    detail: str
    request: ControlledDeploymentCreate
    steps: list[DeploymentStep] = Field(default_factory=list)
    deployed_commit_sha: str = ""
    rollback_target_sha: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_targets(self):
        if self.deployed_commit_sha and self.deployed_commit_sha != self.request.evidence.merge_commit_sha:
            raise ValueError("deployed commit must match authorized merge commit")
        return self


class ControlledDeploymentStatus(BaseModel):
    module: str = "executive-controlled-deployment"
    version: str = "20.06"
    workspace_id: str
    total_records: int
    healthy_records: int
    rollback_records: int


class ControlledDeploymentAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: DeploymentState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
