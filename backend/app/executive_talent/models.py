from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class Criticality(str, Enum):
    standard = "standard"
    important = "important"
    critical = "critical"


class Readiness(str, Enum):
    ready_now = "ready_now"
    ready_soon = "ready_soon"
    developing = "developing"
    unavailable = "unavailable"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TalentRole(BaseModel):
    role_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=2, max_length=160)
    owner_id: str = Field(min_length=1, max_length=100)
    criticality: Criticality = Criticality.important
    required_capacity: float = Field(default=1.0, ge=0.1, le=100)
    available_capacity: float = Field(default=1.0, ge=0, le=100)
    required_skills: list[str] = Field(default_factory=list, max_length=30)
    covered_skills: list[str] = Field(default_factory=list, max_length=30)
    retention_risk: RiskLevel = RiskLevel.low


class SuccessorCandidate(BaseModel):
    candidate_id: UUID = Field(default_factory=uuid4)
    role_id: UUID
    person_id: str = Field(min_length=1, max_length=100)
    readiness: Readiness = Readiness.developing
    readiness_score: float = Field(default=50, ge=0, le=100)
    retention_risk: RiskLevel = RiskLevel.low
    development_actions: list[str] = Field(default_factory=list, max_length=20)


class WorkforceScenario(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    probability: float = Field(ge=0, le=1)
    capacity_impact: float = Field(ge=0, le=100)
    affected_role_ids: list[UUID] = Field(default_factory=list)
    mitigation_strength: float = Field(default=0, ge=0, le=100)


class TalentPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=2, max_length=160)
    executive_owner_id: str = Field(min_length=1, max_length=100)
    strategy_plan_id: UUID | None = None
    transformation_portfolio_id: UUID | None = None
    capital_portfolio_id: UUID | None = None
    roles: list[TalentRole] = Field(min_length=1, max_length=100)
    successors: list[SuccessorCandidate] = Field(default_factory=list, max_length=300)
    scenarios: list[WorkforceScenario] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_references(self):
        role_ids = [role.role_id for role in self.roles]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("Duplicate role identifiers are not allowed")
        known = set(role_ids)
        if any(item.role_id not in known for item in self.successors):
            raise ValueError("Successor references unknown role")
        if any(any(role_id not in known for role_id in scenario.affected_role_ids) for scenario in self.scenarios):
            raise ValueError("Scenario references unknown role")
        return self


class TalentUpdate(BaseModel):
    role_id: UUID
    available_capacity: float | None = Field(default=None, ge=0, le=100)
    retention_risk: RiskLevel | None = None
    candidate_id: UUID | None = None
    readiness: Readiness | None = None
    readiness_score: float | None = Field(default=None, ge=0, le=100)
    actor_id: str = Field(min_length=1, max_length=100)


class ExecutiveTalentPortfolio(BaseModel):
    portfolio_id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    executive_owner_id: str
    strategy_plan_id: UUID | None = None
    transformation_portfolio_id: UUID | None = None
    capital_portfolio_id: UUID | None = None
    roles: list[TalentRole]
    successors: list[SuccessorCandidate]
    scenarios: list[WorkforceScenario]
    capacity_coverage_score: float = 0
    skill_coverage_score: float = 0
    succession_readiness_score: float = 0
    retention_exposure_score: float = 0
    workforce_resilience_score: float = 0
    critical_role_gaps: list[UUID] = Field(default_factory=list)
    executive_actions: list[str] = Field(default_factory=list)
    autonomous_actions_enabled: bool = False
    assessed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TalentStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    critical_roles: int
    uncovered_critical_roles: int
    average_resilience_score: float
    autonomous_actions_enabled: bool = False


class TalentListResponse(BaseModel):
    items: list[ExecutiveTalentPortfolio]
    count: int


class AuditRecord(BaseModel):
    record_id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    portfolio_id: UUID
    action: str
    actor_id: str
    details: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
