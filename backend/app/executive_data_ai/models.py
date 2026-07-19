from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class AISystemRisk(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class DataProduct(BaseModel):
    data_product_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    owner_id: str = Field(min_length=1, max_length=100)
    business_criticality: float = Field(ge=0, le=100)
    quality_score: float = Field(ge=0, le=100)
    lineage_coverage: float = Field(ge=0, le=100)
    access_control_score: float = Field(ge=0, le=100)
    privacy_risk: float = Field(ge=0, le=100)


class AISystem(BaseModel):
    ai_system_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    owner_id: str = Field(min_length=1, max_length=100)
    risk_level: AISystemRisk
    business_impact: float = Field(ge=0, le=100)
    model_performance: float = Field(ge=0, le=100)
    explainability: float = Field(ge=0, le=100)
    human_oversight: float = Field(ge=0, le=100)
    compliance_readiness: float = Field(ge=0, le=100)
    bias_risk: float = Field(ge=0, le=100)
    drift_risk: float = Field(ge=0, le=100)


class GovernanceIssue(BaseModel):
    issue_id: str = Field(min_length=1, max_length=100)
    asset_id: str = Field(min_length=1, max_length=100)
    severity: float = Field(ge=0, le=100)
    remediation_progress: float = Field(ge=0, le=100)
    description: str = Field(min_length=1, max_length=500)


class DataAIPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=100)
    strategy_plan_id: UUID | None = None
    product_portfolio_id: UUID | None = None
    ecosystem_portfolio_id: UUID | None = None
    data_products: list[DataProduct] = Field(default_factory=list)
    ai_systems: list[AISystem] = Field(default_factory=list)
    issues: list[GovernanceIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self):
        groups = (
            (self.data_products, "data_product_id", "data product"),
            (self.ai_systems, "ai_system_id", "AI system"),
            (self.issues, "issue_id", "issue"),
        )
        for values, field, label in groups:
            ids = [getattr(value, field) for value in values]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {label} id")
        return self


class GovernanceUpdate(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    issue_id: str = Field(min_length=1, max_length=100)
    remediation_progress: float = Field(ge=0, le=100)


class ExecutiveDataAIPortfolio(DataAIPortfolioCreate):
    portfolio_id: UUID = Field(default_factory=uuid4)
    data_governance_score: float = 0
    ai_governance_score: float = 0
    compliance_exposure: float = 0
    model_risk_exposure: float = 0
    critical_data_products: list[str] = Field(default_factory=list)
    high_risk_ai_systems: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    assessed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    autonomous_actions_enabled: bool = False


class DataAIListResponse(BaseModel):
    items: list[ExecutiveDataAIPortfolio]
    count: int


class DataAIStatusResponse(BaseModel):
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
