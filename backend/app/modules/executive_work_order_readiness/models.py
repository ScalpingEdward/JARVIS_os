from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class WorkOrderReadinessState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    READINESS_PENDING = "readiness-pending"
    DEPENDENCY_BLOCKED = "dependency-blocked"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    READY = "ready"
    ISSUED = "issued"
    ACCEPTED_BY_ENGINEERING = "accepted-by-engineering"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ARCHIVED = "archived"
    FAILED = "failed"


class ContinuityEvidence(BaseModel):
    reconciliation_record_id: str = Field(min_length=1)
    reconciliation_state: str = Field(min_length=1)
    continuity_token: str = Field(min_length=8)
    handoff_token: str = Field(min_length=8)
    evidence_digest: str = Field(min_length=8)
    objective: str = Field(min_length=1)
    scope: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    priority_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    effort_points: int = Field(ge=1)
    human_approved: bool = False


class WorkOrderReadinessCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    v20_11_continuity_confirmed: bool = False
    upstream_risk_brain_blocked: bool = False
    evidence: ContinuityEvidence
    dependency_status: dict[str, bool] = Field(default_factory=dict)


class EngineeringWorkOrder(BaseModel):
    objective: str
    scope: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    priority_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    effort_points: int = Field(ge=1)
    continuity_token: str
    evidence_digest: str
    execution_boundary: str = "engineering-only"


class WorkOrderReadinessRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: WorkOrderReadinessState
    detail: str
    request: WorkOrderReadinessCreate
    work_order: EngineeringWorkOrder | None = None
    readiness_score: float = Field(default=0, ge=0, le=100)
    issuance_token: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkOrderReadinessExecuteRequest(BaseModel):
    action: str
    actor_id: str = Field(min_length=1)
    human_approved: bool = False
    engineering_receipt_id: str | None = None


class WorkOrderReadinessAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: WorkOrderReadinessState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkOrderReadinessStatus(BaseModel):
    workspace_id: str
    total_records: int
    ready_records: int
    issued_records: int
    accepted_records: int
    blocked_records: int
