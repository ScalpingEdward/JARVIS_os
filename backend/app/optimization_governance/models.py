from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class CandidateStatus(str, Enum):
    draft = "draft"
    analyzed = "analyzed"
    pending_approval = "pending-approval"
    approved = "approved"
    rejected = "rejected"
    archived = "archived"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ApprovalDecision(str, Enum):
    approve = "approve"
    reject = "reject"


class MetricImpact(BaseModel):
    metric: str = Field(min_length=1, max_length=100)
    baseline: float
    expected: float
    weight: float = Field(default=1.0, gt=0, le=10)


class OptimizationVariant(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    implementation_cost: float = Field(default=0, ge=0)
    estimated_hours: float = Field(default=0, ge=0)
    risk_level: RiskLevel = RiskLevel.medium
    metric_impacts: list[MetricImpact] = Field(default_factory=list)
    rollout_steps: list[str] = Field(default_factory=list)
    rollback_steps: list[str] = Field(default_factory=list)


class OptimizationCandidateCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    target_type: str = Field(min_length=1, max_length=80)
    target_id: str = Field(min_length=1, max_length=160)
    source_recommendation_ids: list[UUID] = Field(default_factory=list)
    variants: list[OptimizationVariant] = Field(min_length=1)
    conflict_keys: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_variants(self):
        keys = [variant.key for variant in self.variants]
        if len(keys) != len(set(keys)):
            raise ValueError("Variant keys must be unique")
        return self


class VariantScore(BaseModel):
    variant_key: str
    expected_gain: float
    risk_score: float
    cost_score: float
    roi_score: float
    confidence: float
    total_score: float
    explanation: list[str]


class ConflictRecord(BaseModel):
    conflict_key: str
    candidate_ids: list[UUID]
    severity: RiskLevel
    explanation: str


class OptimizationAnalysis(BaseModel):
    analyzed_at: datetime
    ranked_variants: list[VariantScore]
    recommended_variant_key: str
    conflicts: list[ConflictRecord]
    rollout_plan: list[str]
    rollback_plan: list[str]
    requires_human_approval: bool = True
    automatic_application_enabled: bool = False


class OptimizationCandidate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    title: str
    target_type: str
    target_id: str
    source_recommendation_ids: list[UUID]
    variants: list[OptimizationVariant]
    conflict_keys: list[str]
    tags: list[str]
    status: CandidateStatus = CandidateStatus.draft
    analysis: OptimizationAnalysis | None = None
    approved_variant_key: str | None = None
    approved_by: str | None = None
    approval_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class ApprovalRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    reviewer_id: str = Field(min_length=1, max_length=100)
    decision: ApprovalDecision
    reason: str = Field(min_length=3, max_length=1000)
    variant_key: str | None = Field(default=None, max_length=80)


class SimulationComparison(BaseModel):
    candidate_id: UUID
    workspace_id: str
    control_variant: str
    challenger_variant: str
    control_score: float
    challenger_score: float
    expected_delta: float
    recommendation: str
    generated_at: datetime


class GovernanceStatus(BaseModel):
    version: str = "16.1"
    candidates: int
    pending_approval: int
    approved: int
    rejected: int
    conflicts: int
    automatic_application_enabled: bool = False


class CandidateListResponse(BaseModel):
    items: list[OptimizationCandidate]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    candidate_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
