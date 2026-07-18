from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class GoalState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ACHIEVED = "achieved"
    ARCHIVED = "archived"


class PlanState(str, Enum):
    DRAFT = "draft"
    ANALYZED = "analyzed"
    SIMULATED = "simulated"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    EXECUTION_READY = "execution-ready"
    ARCHIVED = "archived"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Objective(BaseModel):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_.:-]+$")
    title: str = Field(min_length=1, max_length=300)
    weight: float = Field(default=1.0, gt=0, le=100)
    success_metric: str = Field(min_length=1, max_length=500)
    target_value: float | None = None


class Constraint(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    hard: bool = True
    value: str | float | int | bool | None = None


class GoalCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    key: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_.:-]+$")
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=10_000)
    objectives: list[Objective] = Field(min_length=1, max_length=100)
    constraints: list[Constraint] = Field(default_factory=list, max_length=100)
    priority: int = Field(default=50, ge=1, le=100)
    human_approved: bool = True
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "GoalCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_external_action:
            raise ValueError("automatic external actions are disabled")
        if len({item.key for item in self.objectives}) != len(self.objectives):
            raise ValueError("objective keys must be unique")
        return self


class GoalRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    key: str
    title: str
    description: str
    objectives: list[Objective]
    constraints: list[Constraint]
    priority: int
    state: GoalState = GoalState.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlanOption(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=5000)
    steps: list[str] = Field(min_length=1, max_length=200)
    required_capabilities: list[str] = Field(default_factory=list, max_length=100)
    estimated_cost: float = Field(default=0.0, ge=0)
    estimated_duration_minutes: int = Field(default=0, ge=0)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    rollback_plan: list[str] = Field(default_factory=list, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    goal_id: UUID
    key: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_.:-]+$")
    title: str = Field(min_length=1, max_length=300)
    options: list[PlanOption] = Field(min_length=2, max_length=20)
    max_cost: float | None = Field(default=None, ge=0)
    max_duration_minutes: int | None = Field(default=None, ge=0)
    knowledge_entity_ids: list[UUID] = Field(default_factory=list, max_length=200)
    mission_template_key: str | None = Field(default=None, max_length=160)
    human_approved: bool = True
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def validate_options(self) -> "PlanCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_external_action:
            raise ValueError("automatic external actions are disabled")
        if len({item.key for item in self.options}) != len(self.options):
            raise ValueError("plan option keys must be unique")
        return self


class OptionEvaluation(BaseModel):
    option_key: str
    objective_score: float
    risk_score: float
    cost_score: float
    duration_score: float
    total_score: float
    feasible: bool
    reasons: list[str]


class SimulationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    plan_id: UUID
    scenario_name: str
    evaluations: list[OptionEvaluation]
    recommended_option_key: str | None
    confidence: float = Field(ge=0, le=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlanRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    goal_id: UUID
    key: str
    title: str
    options: list[PlanOption]
    max_cost: float | None
    max_duration_minutes: int | None
    knowledge_entity_ids: list[UUID]
    mission_template_key: str | None
    state: PlanState = PlanState.DRAFT
    selected_option_key: str | None = None
    decision_explanation: list[str] = Field(default_factory=list)
    approved_by: str | None = None
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SimulationRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=120)
    scenario_name: str = Field(default="baseline", min_length=1, max_length=200)
    risk_weight: float = Field(default=0.35, ge=0, le=1)
    cost_weight: float = Field(default=0.20, ge=0, le=1)
    duration_weight: float = Field(default=0.15, ge=0, le=1)
    objective_weight: float = Field(default=0.30, ge=0, le=1)

    @model_validator(mode="after")
    def validate_weights(self) -> "SimulationRequest":
        total = self.risk_weight + self.cost_weight + self.duration_weight + self.objective_weight
        if abs(total - 1.0) > 0.0001:
            raise ValueError("simulation weights must sum to 1.0")
        return self


class ApprovalRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    reviewer_id: str = Field(min_length=1, max_length=120)
    selected_option_key: str = Field(min_length=1, max_length=120)


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    target_type: str
    target_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlanningStatus(BaseModel):
    service: str = "planning-intelligence"
    version: str = "15.0"
    goals: int
    plans: int
    simulations: int
    execution_ready_plans: int
    autonomous_execution_enabled: bool = False
    external_actions_enabled: bool = False
    human_approval_required: bool = True
    workspace_isolation: bool = True
