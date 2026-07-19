from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ExposureType(str, Enum):
    revenue = "revenue"
    operations = "operations"
    supplier = "supplier"
    workforce = "workforce"
    data = "data"
    capital = "capital"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class EventStatus(str, Enum):
    monitoring = "monitoring"
    active = "active"
    contained = "contained"
    closed = "closed"


class CountryExposure(BaseModel):
    exposure_id: str = Field(min_length=1, max_length=100)
    country_code: str = Field(min_length=2, max_length=3)
    country_name: str = Field(min_length=1, max_length=160)
    exposure_type: ExposureType
    annual_value: float = Field(ge=0)
    strategic_criticality: float = Field(ge=0, le=100)
    political_stability_score: float = Field(ge=0, le=100)
    sanctions_exposure_score: float = Field(ge=0, le=100)
    fx_transfer_risk_score: float = Field(ge=0, le=100)
    supply_dependency_score: float = Field(ge=0, le=100)
    continuity_readiness_score: float = Field(ge=0, le=100)
    substitutability_score: float = Field(ge=0, le=100)


class GeopoliticalEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=240)
    severity: Severity
    probability: float = Field(ge=0, le=1)
    velocity_score: float = Field(ge=0, le=100)
    exposure_ids: list[str] = Field(default_factory=list)
    status: EventStatus = EventStatus.monitoring
    mitigation_progress: float = Field(default=0, ge=0, le=100)
    response_readiness_score: float = Field(default=0, ge=0, le=100)


class ContinuityOption(BaseModel):
    option_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    exposure_ids: list[str] = Field(default_factory=list)
    activation_readiness_score: float = Field(ge=0, le=100)
    lead_time_days: int = Field(ge=0)
    estimated_cost: float = Field(ge=0)
    capacity_coverage_score: float = Field(ge=0, le=100)


class GeopoliticalPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    executive_owner_id: str = Field(min_length=1, max_length=100)
    strategy_portfolio_id: UUID | None = None
    procurement_portfolio_id: UUID | None = None
    regulatory_portfolio_id: UUID | None = None
    reputation_portfolio_id: UUID | None = None
    exposures: list[CountryExposure] = Field(min_length=1)
    events: list[GeopoliticalEvent] = Field(default_factory=list)
    continuity_options: list[ContinuityOption] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "GeopoliticalPortfolioCreate":
        exposure_ids = [item.exposure_id for item in self.exposures]
        if len(exposure_ids) != len(set(exposure_ids)):
            raise ValueError("Duplicate country exposure IDs are not allowed")
        event_ids = [item.event_id for item in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("Duplicate geopolitical event IDs are not allowed")
        option_ids = [item.option_id for item in self.continuity_options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("Duplicate continuity option IDs are not allowed")
        known = set(exposure_ids)
        for event in self.events:
            missing = set(event.exposure_ids) - known
            if missing:
                raise ValueError(f"Unknown country exposures: {sorted(missing)}")
        for option in self.continuity_options:
            missing = set(option.exposure_ids) - known
            if missing:
                raise ValueError(f"Unknown country exposures: {sorted(missing)}")
        return self


class GeopoliticalEventUpdate(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)
    status: EventStatus | None = None
    mitigation_progress: float = Field(ge=0, le=100)
    response_readiness_score: float | None = Field(default=None, ge=0, le=100)
    actor_id: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1000)


class GeopoliticalAssessment(BaseModel):
    geopolitical_resilience_score: float = Field(ge=0, le=100)
    political_stability_score: float = Field(ge=0, le=100)
    sanctions_exposure_score: float = Field(ge=0, le=100)
    transfer_risk_score: float = Field(ge=0, le=100)
    supply_continuity_score: float = Field(ge=0, le=100)
    event_exposure_score: float = Field(ge=0, le=100)
    response_readiness_score: float = Field(ge=0, le=100)
    vulnerable_exposures: list[str] = Field(default_factory=list)
    priority_events: list[str] = Field(default_factory=list)
    executive_actions: list[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutiveGeopoliticalPortfolio(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    executive_owner_id: str
    strategy_portfolio_id: UUID | None = None
    procurement_portfolio_id: UUID | None = None
    regulatory_portfolio_id: UUID | None = None
    reputation_portfolio_id: UUID | None = None
    exposures: list[CountryExposure]
    events: list[GeopoliticalEvent]
    continuity_options: list[ContinuityOption]
    assessment: GeopoliticalAssessment | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GeopoliticalStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    country_exposures: int
    active_events: int
    critical_events: int
    autonomous_actions_enabled: bool = False


class GeopoliticalListResponse(BaseModel):
    items: list[ExecutiveGeopoliticalPortfolio]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    resource_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
