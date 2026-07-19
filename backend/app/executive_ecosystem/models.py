from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PartnershipType(str, Enum):
    supplier = "supplier"
    channel = "channel"
    technology = "technology"
    alliance = "alliance"
    joint_venture = "joint_venture"


class DependencyLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class PartnerProfile(BaseModel):
    partner_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    partnership_type: PartnershipType
    annual_value: float = Field(ge=0)
    joint_value_potential: float = Field(ge=0)
    strategic_alignment: float = Field(ge=0, le=100)
    performance_score: float = Field(ge=0, le=100)
    trust_score: float = Field(ge=0, le=100)
    dependency_level: DependencyLevel
    substitution_difficulty: float = Field(ge=0, le=100)
    contract_criticality: float = Field(ge=0, le=100)
    concentration_share: float = Field(ge=0, le=100)


class PartnershipSignal(BaseModel):
    signal_id: str = Field(min_length=1, max_length=100)
    partner_id: str = Field(min_length=1, max_length=100)
    risk_probability: float = Field(ge=0, le=100)
    impact: float = Field(ge=0, le=100)
    opportunity_score: float = Field(ge=0, le=100)
    description: str = Field(min_length=1, max_length=500)


class EcosystemPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=100)
    strategy_plan_id: UUID | None = None
    product_portfolio_id: UUID | None = None
    market_portfolio_id: UUID | None = None
    partners: list[PartnerProfile] = Field(min_length=1)
    signals: list[PartnershipSignal] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self):
        partner_ids = [partner.partner_id for partner in self.partners]
        if len(partner_ids) != len(set(partner_ids)):
            raise ValueError("Duplicate partner id")
        signal_ids = [signal.signal_id for signal in self.signals]
        if len(signal_ids) != len(set(signal_ids)):
            raise ValueError("Duplicate signal id")
        unknown = {signal.partner_id for signal in self.signals} - set(partner_ids)
        if unknown:
            raise ValueError("Partnership signal references unknown partner")
        return self


class PartnershipUpdate(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    partner_id: str = Field(min_length=1, max_length=100)
    performance_score: float | None = Field(default=None, ge=0, le=100)
    trust_score: float | None = Field(default=None, ge=0, le=100)
    joint_value_potential: float | None = Field(default=None, ge=0)


class ExecutiveEcosystemPortfolio(EcosystemPortfolioCreate):
    portfolio_id: UUID = Field(default_factory=uuid4)
    ecosystem_health_score: float = 0
    dependency_risk_score: float = 0
    partnership_value_score: float = 0
    concentration_risk_score: float = 0
    total_annual_value: float = 0
    total_joint_value_potential: float = 0
    critical_partners: list[str] = Field(default_factory=list)
    growth_partners: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    assessed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    autonomous_actions_enabled: bool = False


class EcosystemListResponse(BaseModel):
    items: list[ExecutiveEcosystemPortfolio]
    count: int


class EcosystemStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    assessed_portfolios: int
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    actor_id: str
    action: str
    portfolio_id: UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
