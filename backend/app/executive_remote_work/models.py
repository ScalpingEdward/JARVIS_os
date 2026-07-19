from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class OpportunityType(str, Enum):
    employment = "employment"
    freelance = "freelance"
    contract = "contract"
    agency = "agency"
    marketplace = "marketplace"


class DeliveryMode(str, Enum):
    human_led = "human_led"
    ai_assisted = "ai_assisted"
    automation_eligible = "automation_eligible"


class RemoteOpportunity(BaseModel):
    opportunity_id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=2, max_length=160)
    source: str = Field(min_length=2, max_length=100)
    opportunity_type: OpportunityType
    compensation_eur: float = Field(ge=0)
    estimated_hours: float = Field(gt=0)
    skill_fit: float = Field(ge=0, le=100)
    ai_automation_fit: float = Field(ge=0, le=100)
    delivery_confidence: float = Field(ge=0, le=100)
    client_quality: float = Field(ge=0, le=100)
    contract_clarity: float = Field(ge=0, le=100)
    delivery_mode: DeliveryMode = DeliveryMode.ai_assisted
    ai_use_permitted: bool = False

    @property
    def effective_hourly_rate(self) -> float:
        return round(self.compensation_eur / self.estimated_hours, 2)


class DeliveryEngagement(BaseModel):
    engagement_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=2, max_length=160)
    committed_hours: float = Field(ge=0)
    capacity_limit_hours: float = Field(gt=0)
    quality_score: float = Field(ge=0, le=100)
    deadline_readiness: float = Field(ge=0, le=100)
    margin_percent: float = Field(ge=-100, le=100)
    client_satisfaction: float = Field(ge=0, le=100)


class RemoteWorkRisk(BaseModel):
    risk_id: UUID = Field(default_factory=uuid4)
    category: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=4, max_length=500)
    severity: float = Field(ge=0, le=100)
    probability: float = Field(ge=0, le=100)
    impact: float = Field(ge=0, le=100)
    remediation_progress: float = Field(default=0, ge=0, le=100)


class RemoteWorkRiskUpdate(BaseModel):
    risk_id: UUID
    remediation_progress: float = Field(ge=0, le=100)


class RemoteWorkPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=2, max_length=160)
    opportunities: list[RemoteOpportunity] = Field(default_factory=list)
    engagements: list[DeliveryEngagement] = Field(default_factory=list)
    risks: list[RemoteWorkRisk] = Field(default_factory=list)
    strategy_portfolio_id: UUID | None = None
    digital_venture_portfolio_id: UUID | None = None

    @model_validator(mode="after")
    def validate_unique_ids(self):
        for items, attr in ((self.opportunities, "opportunity_id"), (self.engagements, "engagement_id"), (self.risks, "risk_id")):
            values = [getattr(item, attr) for item in items]
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {attr}")
        return self


class ExecutiveRemoteWorkPortfolio(RemoteWorkPortfolioCreate):
    portfolio_id: UUID = Field(default_factory=uuid4)
    opportunity_quality_score: float = 0
    delivery_capacity_score: float = 0
    profitability_score: float = 0
    ethical_readiness_score: float = 0
    risk_exposure_score: float = 0
    priority_opportunity_ids: list[UUID] = Field(default_factory=list)
    priority_risk_ids: list[UUID] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    assessed_at: datetime | None = None


class RemoteWorkStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    autonomous_application_enabled: bool = False
    autonomous_identity_representation_enabled: bool = False
    autonomous_delivery_enabled: bool = False


class RemoteWorkListResponse(BaseModel):
    items: list[ExecutiveRemoteWorkPortfolio]
    count: int


class AuditRecord(BaseModel):
    audit_id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    portfolio_id: UUID
    action: str
    actor_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
