from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class DecisionStatus(str, Enum):
    draft = "draft"
    analyzed = "analyzed"
    pending_approval = "pending-approval"
    approved = "approved"
    rejected = "rejected"
    archived = "archived"


class PriorityLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class DecisionType(str, Enum):
    coordinate = "coordinate"
    prioritize = "prioritize"
    defer = "defer"
    escalate = "escalate"
    resolve_conflict = "resolve-conflict"


class ApprovalDecision(str, Enum):
    approve = "approve"
    reject = "reject"


class ModuleSignal(BaseModel):
    module: str = Field(min_length=1, max_length=100)
    signal_type: str = Field(min_length=1, max_length=100)
    reference_id: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1000)
    urgency: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)
    risk: float = Field(default=0.5, ge=0, le=1)
    expected_value: float = Field(default=0.5, ge=0, le=1)
    dependencies: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class StrategicConstraint(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    hard: bool = True


class CoreDecisionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=2000)
    signals: list[ModuleSignal] = Field(min_length=1)
    constraints: list[StrategicConstraint] = Field(default_factory=list)
    available_capabilities: list[str] = Field(default_factory=list)
    max_parallel_actions: int = Field(default=3, ge=1, le=100)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_signal_references(self):
        refs = [signal.reference_id for signal in self.signals]
        if len(refs) != len(set(refs)):
            raise ValueError("Signal reference IDs must be unique")
        return self


class GoalNode(BaseModel):
    key: str
    title: str
    parent_key: str | None = None
    priority: PriorityLevel
    source_references: list[str]


class ArbitrationScore(BaseModel):
    reference_id: str
    module: str
    priority_score: float
    urgency_score: float
    value_score: float
    confidence_score: float
    risk_penalty: float
    dependency_penalty: float
    capability_penalty: float
    total_score: float
    rank: int
    explanation: list[str]


class DecisionConflict(BaseModel):
    key: str
    reference_ids: list[str]
    severity: PriorityLevel
    explanation: str
    resolution: str


class UnifiedTask(BaseModel):
    task_key: str
    source_reference_id: str
    module: str
    sequence: int
    priority: PriorityLevel
    dependencies: list[str]
    required_capabilities: list[str]
    blocked: bool
    block_reasons: list[str]
    requires_human_approval: bool = True


class ExecutiveRecommendation(BaseModel):
    decision_type: DecisionType
    title: str
    rationale: str
    affected_references: list[str]
    confidence: float
    requires_human_approval: bool = True


class CoreAnalysis(BaseModel):
    analyzed_at: datetime
    decomposed_goals: list[GoalNode]
    arbitration: list[ArbitrationScore]
    conflicts: list[DecisionConflict]
    unified_task_graph: list[UnifiedTask]
    recommended_sequence: list[str]
    deferred_references: list[str]
    executive_recommendations: list[ExecutiveRecommendation]
    global_confidence: float
    decision_summary: str
    requires_human_approval: bool = True
    autonomous_execution_enabled: bool = False


class CoreDecision(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    title: str
    objective: str
    signals: list[ModuleSignal]
    constraints: list[StrategicConstraint]
    available_capabilities: list[str]
    max_parallel_actions: int
    tags: list[str]
    status: DecisionStatus = DecisionStatus.draft
    analysis: CoreAnalysis | None = None
    approved_by: str | None = None
    approval_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class DecisionApprovalRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    reviewer_id: str = Field(min_length=1, max_length=100)
    decision: ApprovalDecision
    reason: str = Field(min_length=3, max_length=1000)


class CoreStatus(BaseModel):
    version: str = "17.0"
    decisions: int
    analyzed: int
    pending_approval: int
    approved: int
    rejected: int
    conflicts: int
    autonomous_execution_enabled: bool = False


class CoreDecisionListResponse(BaseModel):
    items: list[CoreDecision]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    decision_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
