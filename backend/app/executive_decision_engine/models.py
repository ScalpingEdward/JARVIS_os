from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class DecisionStatus(str, Enum):
    draft = "draft"
    evaluated = "evaluated"
    approved = "approved"
    rejected = "rejected"


class ConstraintType(str, Enum):
    required = "required"
    maximum = "maximum"
    minimum = "minimum"


class DecisionCriterion(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    weight: float = Field(gt=0, le=100)
    description: str = Field(default="", max_length=500)


class DecisionConstraint(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    constraint_type: ConstraintType
    field_name: str = Field(min_length=1, max_length=120)
    value: float | bool | str
    blocking: bool = True


class DecisionAlternative(BaseModel):
    alternative_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    criterion_scores: dict[str, float] = Field(default_factory=dict)
    attributes: dict[str, float | bool | str] = Field(default_factory=dict)
    confidence: float = Field(default=50, ge=0, le=100)
    risk_score: float = Field(default=0, ge=0, le=100)
    implementation_cost: float = Field(default=0, ge=0)
    expected_value: float = 0
    notes: list[str] = Field(default_factory=list)


class ExecutiveDecisionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=1000)
    criteria: list[DecisionCriterion] = Field(min_length=1)
    alternatives: list[DecisionAlternative] = Field(min_length=2)
    constraints: list[DecisionConstraint] = Field(default_factory=list)
    source_briefing_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_decision(self):
        criterion_names = [item.name for item in self.criteria]
        if len(criterion_names) != len(set(criterion_names)):
            raise ValueError("Criterion names must be unique")
        if abs(sum(item.weight for item in self.criteria) - 100.0) > 0.01:
            raise ValueError("Criterion weights must total 100")
        keys = [item.alternative_key for item in self.alternatives]
        if len(keys) != len(set(keys)):
            raise ValueError("Alternative keys must be unique")
        known = set(criterion_names)
        for alternative in self.alternatives:
            unknown = set(alternative.criterion_scores) - known
            if unknown:
                raise ValueError(f"Unknown criterion scores: {sorted(unknown)}")
            missing = known - set(alternative.criterion_scores)
            if missing:
                raise ValueError(f"Missing criterion scores: {sorted(missing)}")
            if any(score < 0 or score > 100 for score in alternative.criterion_scores.values()):
                raise ValueError("Criterion scores must be between 0 and 100")
        return self


class ConstraintResult(BaseModel):
    constraint_name: str
    alternative_key: str
    passed: bool
    blocking: bool
    explanation: str


class AlternativeEvaluation(BaseModel):
    alternative_key: str
    title: str
    weighted_score: float = Field(ge=0, le=100)
    adjusted_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    expected_value: float
    implementation_cost: float
    rank: int = Field(ge=1)
    feasible: bool
    trade_offs: list[str]
    score_explanation: dict[str, float]


class DecisionTraceNode(BaseModel):
    node_type: str
    key: str
    label: str
    value: float | str | bool | None = None


class DecisionEvaluation(BaseModel):
    evaluated_at: datetime
    recommended_alternative_key: str | None
    executive_confidence: float = Field(ge=0, le=100)
    evaluations: list[AlternativeEvaluation]
    constraint_results: list[ConstraintResult]
    trace: list[DecisionTraceNode]
    blocking_reasons: list[str]
    executive_summary: str
    approval_required: bool = True
    autonomous_actions_enabled: bool = False


class ApprovalRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    approved: bool
    comment: str = Field(default="", max_length=1000)


class ApprovalRecord(BaseModel):
    actor_id: str
    approved: bool
    comment: str
    created_at: datetime


class ExecutiveDecision(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    title: str
    objective: str
    criteria: list[DecisionCriterion]
    alternatives: list[DecisionAlternative]
    constraints: list[DecisionConstraint]
    source_briefing_ids: list[UUID]
    status: DecisionStatus = DecisionStatus.draft
    version: int = 1
    evaluation: DecisionEvaluation | None = None
    approval: ApprovalRecord | None = None
    created_at: datetime
    updated_at: datetime


class DecisionStatusResponse(BaseModel):
    version: str = "18.2"
    decisions: int
    evaluated_decisions: int
    approved_decisions: int
    blocked_decisions: int
    autonomous_actions_enabled: bool = False


class DecisionListResponse(BaseModel):
    items: list[ExecutiveDecision]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    decision_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
