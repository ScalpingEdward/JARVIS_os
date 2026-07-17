from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ChangeState(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    ROLLED_BACK = "rolled-back"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class ChangeCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    change_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=8000)
    change_type: str = Field(min_length=1, max_length=120)
    risk_level: RiskLevel
    affected_services: list[str] = Field(default_factory=list, max_length=500)
    related_incident_ids: list[UUID] = Field(default_factory=list, max_length=200)
    implementation_plan: str = Field(min_length=1, max_length=12000)
    validation_plan: str = Field(min_length=1, max_length=12000)
    rollback_plan: str = Field(min_length=1, max_length=12000)
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    evidence_references: list[str] = Field(default_factory=list, max_length=500)
    required_approvals: int = Field(default=1, ge=1, le=20)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_approval: bool = False
    execute_change: bool = False
    external_deployment: bool = False

    @model_validator(mode="after")
    def safety(self) -> "ChangeCreate":
        if self.planned_start and self.planned_end and self.planned_end <= self.planned_start:
            raise ValueError("planned_end must be after planned_start")
        if self.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL} and self.required_approvals < 2:
            raise ValueError("high-risk changes require at least two approvals")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_approval:
            raise ValueError("automatic change approval is disabled")
        if self.execute_change:
            raise ValueError("change records never execute deployments")
        if self.external_deployment:
            raise ValueError("external deployment providers are disabled")
        return self


class ChangeRecord(ChangeCreate):
    id: UUID = Field(default_factory=uuid4)
    state: ChangeState = ChangeState.DRAFT
    approval_count: int = 0
    rejection_count: int = 0
    implemented_at: datetime | None = None
    verified_at: datetime | None = None
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
    change_id: UUID
    decision: ApprovalDecision
    comment: str = Field(default="", max_length=4000)
    human_approved: bool = True
    automatic_decision: bool = False

    @model_validator(mode="after")
    def safety(self) -> "ApprovalCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_decision:
            raise ValueError("automatic approval decisions are disabled")
        return self


class ApprovalRecord(ApprovalCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReleaseCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    change_id: UUID
    release_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    environment: str = Field(min_length=1, max_length=120)
    artifact_reference: str = Field(min_length=1, max_length=1000)
    scheduled_start: datetime
    scheduled_end: datetime
    human_approved: bool = True
    execute_release: bool = False

    @model_validator(mode="after")
    def safety(self) -> "ReleaseCreate":
        if self.scheduled_end <= self.scheduled_start:
            raise ValueError("scheduled_end must be after scheduled_start")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_release:
            raise ValueError("release plans never execute deployments")
        return self


class ReleaseRecord(ReleaseCreate):
    id: UUID = Field(default_factory=uuid4)
    state: str = "planned"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsRecord(BaseModel):
    workspace_id: str
    changes: int
    pending_review: int
    approved: int
    scheduled: int
    implemented: int
    verified: int
    rolled_back: int
    open_high_risk: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    entity_type: str
    entity_id: UUID | None = None
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChangeGovernanceStatus(BaseModel):
    version: str = "10.3"
    changes: int
    approvals: int
    releases: int
    automatic_approval_enabled: bool = False
    executes_deployments: bool = False
    external_deployment_enabled: bool = False
