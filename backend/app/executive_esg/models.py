from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class EsgPillar(str, Enum):
    environmental = "environmental"
    social = "social"
    governance = "governance"


class EsgMetric(BaseModel):
    metric_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    pillar: EsgPillar
    current_value: float
    target_value: float
    weight: float = Field(gt=0, le=100)
    data_quality: float = Field(ge=0, le=100)
    regulatory_materiality: float = Field(ge=0, le=100)


class SustainabilityInitiative(BaseModel):
    initiative_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    pillar: EsgPillar
    investment_required: float = Field(ge=0)
    expected_annual_savings: float = Field(ge=0)
    impact_score: float = Field(ge=0, le=100)
    execution_readiness: float = Field(ge=0, le=100)
    delivery_risk: float = Field(ge=0, le=100)


class EsgIssue(BaseModel):
    issue_id: str = Field(min_length=1, max_length=100)
    pillar: EsgPillar
    severity: float = Field(ge=0, le=100)
    remediation_progress: float = Field(ge=0, le=100)
    description: str = Field(min_length=1, max_length=500)


class EsgPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=100)
    strategy_plan_id: UUID | None = None
    product_portfolio_id: UUID | None = None
    data_ai_portfolio_id: UUID | None = None
    metrics: list[EsgMetric] = Field(min_length=1)
    initiatives: list[SustainabilityInitiative] = Field(default_factory=list)
    issues: list[EsgIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self):
        groups = ((self.metrics, "metric_id"), (self.initiatives, "initiative_id"), (self.issues, "issue_id"))
        for values, field in groups:
            ids = [getattr(value, field) for value in values]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {field}")
        return self


class EsgIssueUpdate(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    issue_id: str = Field(min_length=1, max_length=100)
    remediation_progress: float = Field(ge=0, le=100)


class ExecutiveEsgPortfolio(EsgPortfolioCreate):
    portfolio_id: UUID = Field(default_factory=uuid4)
    environmental_score: float = 0
    social_score: float = 0
    governance_score: float = 0
    overall_esg_score: float = 0
    compliance_exposure: float = 0
    initiative_value_score: float = 0
    material_gaps: list[str] = Field(default_factory=list)
    priority_initiatives: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    assessed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    autonomous_actions_enabled: bool = False


class EsgListResponse(BaseModel):
    items: list[ExecutiveEsgPortfolio]
    count: int


class EsgStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    assessed_portfolios: int
    material_gaps: int
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    actor_id: str
    action: str
    portfolio_id: UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
