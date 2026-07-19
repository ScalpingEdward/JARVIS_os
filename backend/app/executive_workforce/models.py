from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class WorkforceCriticality(str, Enum):
    standard = "standard"
    important = "important"
    critical = "critical"


class WorkforceSegment(BaseModel):
    segment_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    headcount: int = Field(ge=0, le=1000000)
    criticality: WorkforceCriticality = WorkforceCriticality.standard
    capacity_utilization: float = Field(ge=0, le=1.5)
    engagement_score: float = Field(ge=0, le=100)
    retention_risk: float = Field(ge=0, le=1)
    skill_coverage: float = Field(ge=0, le=1)
    succession_coverage: float = Field(ge=0, le=1)
    vacancy_rate: float = Field(ge=0, le=1)


class CriticalRole(BaseModel):
    role_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    segment_id: str = Field(min_length=1, max_length=100)
    incumbents: int = Field(ge=0, le=100000)
    required_incumbents: int = Field(gt=0, le=100000)
    ready_successors: int = Field(ge=0, le=100000)
    time_to_fill_days: int = Field(ge=0, le=3650)
    business_impact: float = Field(ge=0, le=1)
    attrition_risk: float = Field(ge=0, le=1)


class TalentRisk(BaseModel):
    risk_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    severity: float = Field(ge=0, le=1)
    probability: float = Field(ge=0, le=1)
    affected_segment_ids: list[str] = Field(default_factory=list)
    remediation_progress: float = Field(default=0, ge=0, le=1)


class WorkforcePortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    executive_owner_id: str = Field(min_length=1, max_length=100)
    strategy_portfolio_id: UUID | None = None
    regulatory_portfolio_id: UUID | None = None
    esg_portfolio_id: UUID | None = None
    segments: list[WorkforceSegment] = Field(min_length=1)
    critical_roles: list[CriticalRole] = Field(default_factory=list)
    risks: list[TalentRisk] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "WorkforcePortfolioCreate":
        segment_ids = [item.segment_id for item in self.segments]
        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError("Duplicate workforce segment IDs are not allowed")
        role_ids = [item.role_id for item in self.critical_roles]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("Duplicate critical role IDs are not allowed")
        risk_ids = [item.risk_id for item in self.risks]
        if len(risk_ids) != len(set(risk_ids)):
            raise ValueError("Duplicate talent risk IDs are not allowed")
        known = set(segment_ids)
        for role in self.critical_roles:
            if role.segment_id not in known:
                raise ValueError(f"Unknown role segment: {role.segment_id}")
        for risk in self.risks:
            missing = set(risk.affected_segment_ids) - known
            if missing:
                raise ValueError(f"Unknown affected workforce segments: {sorted(missing)}")
        return self


class TalentRiskUpdate(BaseModel):
    risk_id: str = Field(min_length=1, max_length=100)
    remediation_progress: float = Field(ge=0, le=1)
    actor_id: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1000)


class WorkforceAssessment(BaseModel):
    workforce_health_score: float = Field(ge=0, le=100)
    capacity_resilience_score: float = Field(ge=0, le=100)
    skill_readiness_score: float = Field(ge=0, le=100)
    succession_readiness_score: float = Field(ge=0, le=100)
    retention_exposure_score: float = Field(ge=0, le=100)
    critical_segments: list[str] = Field(default_factory=list)
    vulnerable_roles: list[str] = Field(default_factory=list)
    priority_risks: list[str] = Field(default_factory=list)
    executive_actions: list[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutiveWorkforcePortfolio(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    executive_owner_id: str
    strategy_portfolio_id: UUID | None = None
    regulatory_portfolio_id: UUID | None = None
    esg_portfolio_id: UUID | None = None
    segments: list[WorkforceSegment]
    critical_roles: list[CriticalRole]
    risks: list[TalentRisk]
    assessment: WorkforceAssessment | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkforceStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    total_headcount: int
    critical_segments: int
    high_retention_risk_segments: int
    autonomous_actions_enabled: bool = False


class WorkforceListResponse(BaseModel):
    items: list[ExecutiveWorkforcePortfolio]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    resource_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
