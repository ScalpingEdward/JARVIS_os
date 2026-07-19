from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class DealStage(str, Enum):
    diligence = "diligence"
    signing = "signing"
    closing = "closing"
    day_1 = "day_1"
    integration = "integration"
    stabilized = "stabilized"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IntegrationWorkstream(BaseModel):
    workstream_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    owner_id: str = Field(min_length=1, max_length=100)
    progress: float = Field(ge=0, le=100)
    day_1_readiness: float = Field(ge=0, le=100)
    day_100_readiness: float = Field(ge=0, le=100)
    dependency_risk: float = Field(ge=0, le=100)
    tsa_dependency: float = Field(ge=0, le=100)


class SynergyTarget(BaseModel):
    synergy_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    target_value: float = Field(ge=0)
    realized_value: float = Field(default=0, ge=0)
    confidence_score: float = Field(ge=0, le=100)
    timing_readiness: float = Field(ge=0, le=100)


class IntegrationRisk(BaseModel):
    risk_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=240)
    severity: Severity
    probability: float = Field(ge=0, le=1)
    impact_score: float = Field(ge=0, le=100)
    remediation_progress: float = Field(default=0, ge=0, le=100)


class MAPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    executive_owner_id: str = Field(min_length=1, max_length=100)
    deal_stage: DealStage
    purchase_price: float = Field(ge=0)
    strategic_fit_score: float = Field(ge=0, le=100)
    culture_alignment_score: float = Field(ge=0, le=100)
    talent_retention_score: float = Field(ge=0, le=100)
    customer_continuity_score: float = Field(ge=0, le=100)
    strategy_portfolio_id: UUID | None = None
    workforce_portfolio_id: UUID | None = None
    culture_portfolio_id: UUID | None = None
    capital_portfolio_id: UUID | None = None
    workstreams: list[IntegrationWorkstream] = Field(min_length=1)
    synergies: list[SynergyTarget] = Field(default_factory=list)
    risks: list[IntegrationRisk] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "MAPortfolioCreate":
        for values, label in ((self.workstreams, "workstream_id"), (self.synergies, "synergy_id"), (self.risks, "risk_id")):
            ids = [getattr(item, label) for item in values]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {label} values are not allowed")
        return self


class IntegrationRiskUpdate(BaseModel):
    risk_id: str = Field(min_length=1, max_length=100)
    remediation_progress: float = Field(ge=0, le=100)
    actor_id: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1000)


class MAAssessment(BaseModel):
    integration_health_score: float = Field(ge=0, le=100)
    synergy_realization_score: float = Field(ge=0, le=100)
    value_leakage_exposure: float = Field(ge=0, le=100)
    day_1_readiness_score: float = Field(ge=0, le=100)
    day_100_readiness_score: float = Field(ge=0, le=100)
    people_and_culture_score: float = Field(ge=0, le=100)
    priority_workstreams: list[str] = Field(default_factory=list)
    priority_risks: list[str] = Field(default_factory=list)
    executive_actions: list[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutiveMAPortfolio(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    executive_owner_id: str
    deal_stage: DealStage
    purchase_price: float
    strategic_fit_score: float
    culture_alignment_score: float
    talent_retention_score: float
    customer_continuity_score: float
    strategy_portfolio_id: UUID | None = None
    workforce_portfolio_id: UUID | None = None
    culture_portfolio_id: UUID | None = None
    capital_portfolio_id: UUID | None = None
    workstreams: list[IntegrationWorkstream]
    synergies: list[SynergyTarget]
    risks: list[IntegrationRisk]
    assessment: MAAssessment | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MAStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    active_deals: int
    open_risks: int
    critical_risks: int
    autonomous_actions_enabled: bool = False


class MAListResponse(BaseModel):
    items: list[ExecutiveMAPortfolio]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    resource_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
