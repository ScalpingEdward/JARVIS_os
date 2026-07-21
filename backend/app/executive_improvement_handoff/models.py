from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ImprovementHandoffState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    INTAKE_PENDING = "intake-pending"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    READY = "ready"
    HANDED_OFF = "handed-off"
    ACCEPTED_BY_V20_01 = "accepted-by-v20.01"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ARCHIVED = "archived"
    FAILED = "failed"


class BacklogEvidence(BaseModel):
    backlog_record_id: str = Field(min_length=1)
    backlog_state: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    priority_score: float = Field(ge=0, le=100)
    impact_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    effort_points: int = Field(ge=1)
    target_sprint: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    defensive_only: bool = True
    human_approved: bool = False


class ImprovementHandoffCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    v20_09_ready: bool = False
    upstream_risk_brain_blocked: bool = False
    evidence_digest: str = Field(min_length=8)
    evidence: BacklogEvidence


class PlanningIntakePackage(BaseModel):
    objective: str
    scope: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    priority_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    effort_points: int = Field(ge=1)
    evidence_digest: str
    target_module: str = "v20.01"


class ImprovementHandoffRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: ImprovementHandoffState
    detail: str
    request: ImprovementHandoffCreate
    intake_package: PlanningIntakePackage | None = None
    handoff_token: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImprovementHandoffExecuteRequest(BaseModel):
    action: str
    actor_id: str = Field(min_length=1)
    human_approved: bool = False
    v20_01_receipt_id: str | None = None


class ImprovementHandoffAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: ImprovementHandoffState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImprovementHandoffStatus(BaseModel):
    workspace_id: str
    total_records: int
    ready_records: int
    handed_off_records: int
    accepted_records: int
    blocked_records: int
