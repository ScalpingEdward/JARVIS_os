from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ProgramStatus(str, Enum):
    proposed = "proposed"
    active = "active"
    at_risk = "at_risk"
    completed = "completed"


class TransformationBenefit(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    target_value: float
    realized_value: float = 0
    weight: float = Field(gt=0, le=100)


class ChangeReadiness(BaseModel):
    stakeholder_alignment: float = Field(ge=0, le=100)
    capability_readiness: float = Field(ge=0, le=100)
    adoption_readiness: float = Field(ge=0, le=100)
    communication_readiness: float = Field(ge=0, le=100)


class TransformationProgram(BaseModel):
    program_key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    owner_id: str = Field(min_length=1, max_length=100)
    strategic_value: float = Field(ge=0, le=100)
    progress: float = Field(default=0, ge=0, le=100)
    budget: float = Field(default=0, ge=0)
    spent: float = Field(default=0, ge=0)
    risk_score: float = Field(default=0, ge=0, le=100)
    dependencies: list[str] = Field(default_factory=list)
    benefits: list[TransformationBenefit] = Field(default_factory=list)
    readiness: ChangeReadiness


class TransformationPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    strategy_plan_id: UUID | None = None
    governance_framework_id: UUID | None = None
    programs: list[TransformationProgram] = Field(min_length=1)
    portfolio_budget: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_portfolio(self):
        keys = [item.program_key for item in self.programs]
        if len(keys) != len(set(keys)):
            raise ValueError("Program keys must be unique")
        known = set(keys)
        for program in self.programs:
            unknown = set(program.dependencies) - known
            if unknown:
                raise ValueError(f"Unknown program dependencies: {sorted(unknown)}")
            weights = sum(item.weight for item in program.benefits)
            if program.benefits and abs(weights - 100.0) > 0.01:
                raise ValueError("Benefit weights must total 100 per program")
        return self


class ProgramAssessment(BaseModel):
    program_key: str
    health_score: float = Field(ge=0, le=100)
    readiness_score: float = Field(ge=0, le=100)
    benefits_realization: float = Field(ge=0, le=100)
    budget_utilization: float = Field(ge=0)
    status: ProgramStatus
    blockers: list[str]


class TransformationAssessment(BaseModel):
    assessed_at: datetime
    portfolio_health: float = Field(ge=0, le=100)
    benefits_realization: float = Field(ge=0, le=100)
    change_readiness: float = Field(ge=0, le=100)
    budget_utilization: float = Field(ge=0)
    assessments: list[ProgramAssessment]
    critical_path: list[str]
    dependency_blockers: list[str]
    recommendations: list[str]
    executive_summary: str
    autonomous_actions_enabled: bool = False


class ProgressUpdate(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    program_key: str = Field(min_length=1, max_length=100)
    progress: float = Field(ge=0, le=100)
    spent: float = Field(ge=0)
    risk_score: float = Field(ge=0, le=100)
    realized_benefits: dict[str, float] = Field(default_factory=dict)


class ExecutiveTransformationPortfolio(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    title: str
    strategy_plan_id: UUID | None
    governance_framework_id: UUID | None
    programs: list[TransformationProgram]
    portfolio_budget: float
    assessment: TransformationAssessment | None = None
    version: int = 1
    created_at: datetime
    updated_at: datetime


class TransformationStatusResponse(BaseModel):
    version: str = "18.6"
    portfolios: int
    assessed_portfolios: int
    at_risk_programs: int
    autonomous_actions_enabled: bool = False


class TransformationListResponse(BaseModel):
    items: list[ExecutiveTransformationPortfolio]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    portfolio_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
