from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ObligationStatus(str, Enum):
    compliant = "compliant"
    at_risk = "at_risk"
    overdue = "overdue"
    monitoring = "monitoring"


class RegulatoryObligation(BaseModel):
    obligation_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=240)
    jurisdiction: str = Field(min_length=1, max_length=120)
    authority: str = Field(min_length=1, max_length=160)
    owner_id: str = Field(min_length=1, max_length=100)
    materiality: float = Field(ge=0, le=1)
    control_coverage: float = Field(ge=0, le=1)
    evidence_readiness: float = Field(ge=0, le=1)
    implementation_progress: float = Field(ge=0, le=1)
    days_to_deadline: int = Field(ge=-3650, le=3650)
    status: ObligationStatus = ObligationStatus.monitoring


class ComplianceIssue(BaseModel):
    issue_id: str = Field(min_length=1, max_length=100)
    obligation_id: str = Field(min_length=1, max_length=100)
    severity: float = Field(ge=0, le=1)
    remediation_progress: float = Field(default=0, ge=0, le=1)
    financial_exposure: float = Field(default=0, ge=0)
    reputational_exposure: float = Field(default=0, ge=0, le=1)


class RegulatoryPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    executive_owner_id: str = Field(min_length=1, max_length=100)
    strategy_portfolio_id: UUID | None = None
    data_ai_portfolio_id: UUID | None = None
    esg_portfolio_id: UUID | None = None
    obligations: list[RegulatoryObligation] = Field(min_length=1)
    issues: list[ComplianceIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "RegulatoryPortfolioCreate":
        obligation_ids = [item.obligation_id for item in self.obligations]
        if len(obligation_ids) != len(set(obligation_ids)):
            raise ValueError("Duplicate obligation IDs are not allowed")
        issue_ids = [item.issue_id for item in self.issues]
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("Duplicate compliance issue IDs are not allowed")
        known = set(obligation_ids)
        missing = {item.obligation_id for item in self.issues} - known
        if missing:
            raise ValueError(f"Unknown obligation references: {sorted(missing)}")
        return self


class ComplianceIssueUpdate(BaseModel):
    issue_id: str = Field(min_length=1, max_length=100)
    remediation_progress: float = Field(ge=0, le=1)
    actor_id: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1000)


class RegulatoryAssessment(BaseModel):
    compliance_readiness_score: float = Field(ge=0, le=100)
    control_coverage_score: float = Field(ge=0, le=100)
    evidence_readiness_score: float = Field(ge=0, le=100)
    regulatory_exposure_score: float = Field(ge=0, le=100)
    deadline_pressure_score: float = Field(ge=0, le=100)
    obligations_at_risk: list[str] = Field(default_factory=list)
    overdue_obligations: list[str] = Field(default_factory=list)
    priority_issues: list[str] = Field(default_factory=list)
    executive_actions: list[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutiveRegulatoryPortfolio(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    executive_owner_id: str
    strategy_portfolio_id: UUID | None = None
    data_ai_portfolio_id: UUID | None = None
    esg_portfolio_id: UUID | None = None
    obligations: list[RegulatoryObligation]
    issues: list[ComplianceIssue]
    assessment: RegulatoryAssessment | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RegulatoryStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    obligations: int
    obligations_at_risk: int
    overdue_obligations: int
    autonomous_actions_enabled: bool = False


class RegulatoryListResponse(BaseModel):
    items: list[ExecutiveRegulatoryPortfolio]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    resource_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
