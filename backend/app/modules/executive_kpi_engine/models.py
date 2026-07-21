from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ExecutiveKPIState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    KPI_DESIGN_PENDING = "kpi-design-pending"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    KPI_SET_READY = "kpi-set-ready"
    APPROVED = "approved"
    ISSUED_TO_RISK_ANALYSIS = "issued-to-risk-analysis"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"


class RoadmapMilestoneEvidence(BaseModel):
    milestone_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    budget: float = Field(ge=0)
    expected_value: float = Field(ge=0)
    exit_criteria: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    dependency_ready: bool = True


class ExecutiveKPIConfig(BaseModel):
    warning_threshold_pct: float = Field(default=10, ge=0, le=100)
    critical_threshold_pct: float = Field(default=25, ge=0, le=100)
    minimum_confidence: float = Field(default=70, ge=0, le=100)
    measurement_frequency: str = Field(default="weekly", min_length=1)


class ExecutiveKPICreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    v21_05_roadmap_approved: bool = False
    upstream_risk_brain_blocked: bool = False
    roadmap_record_id: str = Field(min_length=1)
    roadmap_state: str = Field(min_length=1)
    roadmap_confidence: float = Field(ge=0, le=100)
    strategic_metrics: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    milestones: list[RoadmapMilestoneEvidence] = Field(default_factory=list)
    config: ExecutiveKPIConfig = Field(default_factory=ExecutiveKPIConfig)


class KPIIndicator(BaseModel):
    key: str
    name: str
    category: str
    owner_role: str
    target_value: float
    warning_value: float
    critical_value: float
    unit: str
    direction: str
    measurement_frequency: str
    source_milestone_id: str | None = None


class ExecutiveKPIRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: ExecutiveKPIState
    detail: str
    request: ExecutiveKPICreate
    indicators: list[KPIIndicator] = Field(default_factory=list)
    coverage_score: float = Field(default=0, ge=0, le=100)
    governance_score: float = Field(default=0, ge=0, le=100)
    approval_token: str | None = None
    issued_receipt_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutiveKPIExecuteRequest(BaseModel):
    action: str
    actor_id: str = Field(min_length=1)
    human_approved: bool = False
    risk_analysis_receipt_id: str | None = None
    resolution_note: str | None = None


class ExecutiveKPIAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: ExecutiveKPIState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutiveKPIStatus(BaseModel):
    workspace_id: str
    total_records: int
    ready_records: int
    approved_records: int
    issued_records: int
    review_records: int
    blocked_records: int
