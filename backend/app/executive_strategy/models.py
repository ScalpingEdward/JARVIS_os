from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class StrategyStatus(str, Enum):
    draft = "draft"
    analyzed = "analyzed"


class StrategicObjective(BaseModel):
    objective_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    weight: float = Field(gt=0, le=100)
    target_value: float = Field(gt=0)
    current_value: float = Field(default=0, ge=0)
    unit: str = Field(default="score", min_length=1, max_length=40)


class StrategicInitiative(BaseModel):
    initiative_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    objective_keys: list[str] = Field(min_length=1)
    dependencies: list[str] = Field(default_factory=list)
    strategic_value: float = Field(default=50, ge=0, le=100)
    confidence: float = Field(default=50, ge=0, le=100)
    risk_score: float = Field(default=0, ge=0, le=100)
    resource_demand: dict[str, float] = Field(default_factory=dict)
    duration_days: int = Field(default=30, ge=1, le=3650)
    milestone_titles: list[str] = Field(default_factory=list)


class StrategicRisk(BaseModel):
    risk_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    probability: float = Field(ge=0, le=100)
    impact: float = Field(ge=0, le=100)
    mitigation: str = Field(default="", max_length=1000)
    initiative_keys: list[str] = Field(default_factory=list)


class ResourcePool(BaseModel):
    resource_key: str = Field(min_length=1, max_length=120)
    capacity: float = Field(gt=0)


class ExecutiveStrategyCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    horizon_days: int = Field(default=365, ge=1, le=3650)
    objectives: list[StrategicObjective] = Field(min_length=1)
    initiatives: list[StrategicInitiative] = Field(min_length=1)
    resources: list[ResourcePool] = Field(default_factory=list)
    risks: list[StrategicRisk] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_strategy(self):
        objective_keys = [item.objective_key for item in self.objectives]
        initiative_keys = [item.initiative_key for item in self.initiatives]
        resource_keys = [item.resource_key for item in self.resources]
        risk_keys = [item.risk_key for item in self.risks]
        for label, values in {
            "objective": objective_keys,
            "initiative": initiative_keys,
            "resource": resource_keys,
            "risk": risk_keys,
        }.items():
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {label} keys are not allowed")
        if abs(sum(item.weight for item in self.objectives) - 100.0) > 0.01:
            raise ValueError("Objective weights must total 100")
        known_objectives = set(objective_keys)
        known_initiatives = set(initiative_keys)
        known_resources = set(resource_keys)
        for initiative in self.initiatives:
            if set(initiative.objective_keys) - known_objectives:
                raise ValueError("Initiatives reference unknown objectives")
            if set(initiative.dependencies) - known_initiatives:
                raise ValueError("Initiatives reference unknown dependencies")
            if initiative.initiative_key in initiative.dependencies:
                raise ValueError("Initiatives cannot depend on themselves")
            if set(initiative.resource_demand) - known_resources:
                raise ValueError("Initiatives reference unknown resources")
        for risk in self.risks:
            if set(risk.initiative_keys) - known_initiatives:
                raise ValueError("Risks reference unknown initiatives")
        return self


class WhatIfRequest(BaseModel):
    resource_capacity_overrides: dict[str, float] = Field(default_factory=dict)
    initiative_risk_overrides: dict[str, float] = Field(default_factory=dict)
    objective_weight_overrides: dict[str, float] = Field(default_factory=dict)


class Milestone(BaseModel):
    initiative_key: str
    title: str
    target_day: int
    completed: bool = False


class InitiativeAnalysis(BaseModel):
    initiative_key: str
    priority_score: float = Field(ge=0, le=100)
    alignment_score: float = Field(ge=0, le=100)
    risk_adjusted_score: float = Field(ge=0, le=100)
    feasible: bool
    blocking_reasons: list[str]
    allocated_resources: dict[str, float]


class StrategicRoadmapItem(BaseModel):
    initiative_key: str
    sequence: int = Field(ge=1)
    start_day: int = Field(ge=0)
    end_day: int = Field(ge=1)
    dependencies: list[str]


class StrategyAnalysis(BaseModel):
    analyzed_at: datetime
    alignment_score: float = Field(ge=0, le=100)
    objective_progress: dict[str, float]
    initiatives: list[InitiativeAnalysis]
    dependency_graph: dict[str, list[str]]
    resource_allocation: dict[str, dict[str, float]]
    risk_register: list[dict]
    roadmap: list[StrategicRoadmapItem]
    milestones: list[Milestone]
    scenario_summary: str
    executive_summary: str
    autonomous_actions_enabled: bool = False


class ExecutiveStrategyPlan(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    title: str
    horizon_days: int
    objectives: list[StrategicObjective]
    initiatives: list[StrategicInitiative]
    resources: list[ResourcePool]
    risks: list[StrategicRisk]
    status: StrategyStatus = StrategyStatus.draft
    version: int = 1
    analysis: StrategyAnalysis | None = None
    created_at: datetime
    updated_at: datetime


class StrategyStatusResponse(BaseModel):
    version: str = "18.3"
    plans: int
    analyzed_plans: int
    average_alignment_score: float = Field(ge=0, le=100)
    autonomous_actions_enabled: bool = False


class StrategyListResponse(BaseModel):
    items: list[ExecutiveStrategyPlan]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    plan_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
