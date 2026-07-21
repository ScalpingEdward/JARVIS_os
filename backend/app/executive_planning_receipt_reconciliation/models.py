from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PlanningReceiptState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    RECONCILIATION_PENDING = "reconciliation-pending"
    DRIFT_DETECTED = "drift-detected"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    RECONCILED = "reconciled"
    CONTINUITY_CONFIRMED = "continuity-confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ARCHIVED = "archived"
    FAILED = "failed"


class HandoffEvidence(BaseModel):
    handoff_record_id: str = Field(min_length=1)
    handoff_state: str = Field(min_length=1)
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


class PlanningReceiptEvidence(BaseModel):
    receipt_id: str = Field(min_length=1)
    target_module: str = Field(default="v20.01", min_length=1)
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
    accepted: bool = False


class PlanningReceiptCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    v20_10_accepted: bool = False
    upstream_risk_brain_blocked: bool = False
    handoff: HandoffEvidence
    receipt: PlanningReceiptEvidence


class ReconciliationFinding(BaseModel):
    field: str
    expected: str
    actual: str
    severity: str


class PlanningReceiptRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: PlanningReceiptState
    detail: str
    request: PlanningReceiptCreate
    findings: list[ReconciliationFinding] = Field(default_factory=list)
    continuity_token: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlanningReceiptExecuteRequest(BaseModel):
    action: str
    actor_id: str = Field(min_length=1)
    human_approved: bool = False
    resolution_note: str | None = None


class PlanningReceiptAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: PlanningReceiptState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlanningReceiptStatus(BaseModel):
    workspace_id: str
    total_records: int
    pending_records: int
    drift_records: int
    reconciled_records: int
    continuity_records: int
    blocked_records: int
