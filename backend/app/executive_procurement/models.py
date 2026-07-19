from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class Criticality(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    severe = "severe"


class Supplier(BaseModel):
    supplier_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=100)
    annual_spend: float = Field(ge=0)
    criticality: Criticality = Criticality.medium
    contract_coverage: float = Field(ge=0, le=1)
    sla_performance: float = Field(ge=0, le=1)
    compliance_score: float = Field(ge=0, le=1)
    cyber_risk: float = Field(ge=0, le=1)
    operational_risk: float = Field(ge=0, le=1)
    financial_risk: float = Field(ge=0, le=1)
    exit_readiness: float = Field(ge=0, le=1)
    substitutability: float = Field(ge=0, le=1)


class ThirdPartyIssue(BaseModel):
    issue_id: str = Field(min_length=1, max_length=100)
    supplier_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    risk_level: RiskLevel = RiskLevel.medium
    probability: float = Field(ge=0, le=1)
    remediation_progress: float = Field(default=0, ge=0, le=1)
    owner_id: str = Field(min_length=1, max_length=100)


class ProcurementPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    executive_owner_id: str = Field(min_length=1, max_length=100)
    strategy_portfolio_id: UUID | None = None
    ecosystem_portfolio_id: UUID | None = None
    regulatory_portfolio_id: UUID | None = None
    suppliers: list[Supplier] = Field(min_length=1)
    issues: list[ThirdPartyIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "ProcurementPortfolioCreate":
        supplier_ids = [item.supplier_id for item in self.suppliers]
        if len(supplier_ids) != len(set(supplier_ids)):
            raise ValueError("Duplicate supplier IDs are not allowed")
        issue_ids = [item.issue_id for item in self.issues]
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("Duplicate issue IDs are not allowed")
        unknown = {item.supplier_id for item in self.issues} - set(supplier_ids)
        if unknown:
            raise ValueError(f"Unknown suppliers referenced by issues: {sorted(unknown)}")
        return self


class ThirdPartyIssueUpdate(BaseModel):
    issue_id: str = Field(min_length=1, max_length=100)
    remediation_progress: float = Field(ge=0, le=1)
    actor_id: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1000)


class ProcurementAssessment(BaseModel):
    supplier_health_score: float = Field(ge=0, le=100)
    contract_governance_score: float = Field(ge=0, le=100)
    concentration_exposure_score: float = Field(ge=0, le=100)
    third_party_risk_score: float = Field(ge=0, le=100)
    exit_readiness_score: float = Field(ge=0, le=100)
    critical_suppliers: list[str] = Field(default_factory=list)
    vulnerable_suppliers: list[str] = Field(default_factory=list)
    priority_issues: list[str] = Field(default_factory=list)
    executive_actions: list[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutiveProcurementPortfolio(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    executive_owner_id: str
    strategy_portfolio_id: UUID | None = None
    ecosystem_portfolio_id: UUID | None = None
    regulatory_portfolio_id: UUID | None = None
    suppliers: list[Supplier]
    issues: list[ThirdPartyIssue]
    assessment: ProcurementAssessment | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProcurementStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    suppliers: int
    critical_suppliers: int
    open_priority_issues: int
    autonomous_actions_enabled: bool = False


class ProcurementListResponse(BaseModel):
    items: list[ExecutiveProcurementPortfolio]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    resource_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
