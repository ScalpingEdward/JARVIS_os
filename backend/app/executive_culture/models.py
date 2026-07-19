from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class CulturalRisk(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ChangeState(str, Enum):
    planned = "planned"
    mobilizing = "mobilizing"
    adopting = "adopting"
    stabilizing = "stabilizing"
    complete = "complete"


class CultureSegment(BaseModel):
    segment_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    population: int = Field(gt=0)
    leadership_alignment: float = Field(ge=0, le=100)
    psychological_safety: float = Field(ge=0, le=100)
    collaboration_score: float = Field(ge=0, le=100)
    accountability_score: float = Field(ge=0, le=100)
    change_fatigue: float = Field(ge=0, le=100)
    trust_score: float = Field(ge=0, le=100)


class ChangeInitiative(BaseModel):
    initiative_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    owner_id: str = Field(min_length=1, max_length=100)
    state: ChangeState = ChangeState.planned
    affected_segment_ids: list[str] = Field(default_factory=list)
    strategic_importance: float = Field(ge=0, le=100)
    sponsor_commitment: float = Field(ge=0, le=100)
    communication_reach: float = Field(ge=0, le=100)
    manager_enablement: float = Field(ge=0, le=100)
    adoption_progress: float = Field(ge=0, le=100)
    resistance_level: float = Field(ge=0, le=100)


class CultureIssue(BaseModel):
    issue_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    risk: CulturalRisk = CulturalRisk.medium
    affected_segment_ids: list[str] = Field(default_factory=list)
    probability: float = Field(ge=0, le=1)
    remediation_progress: float = Field(default=0, ge=0, le=100)


class CulturePortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    executive_owner_id: str = Field(min_length=1, max_length=100)
    strategy_portfolio_id: UUID | None = None
    workforce_portfolio_id: UUID | None = None
    transformation_portfolio_id: UUID | None = None
    segments: list[CultureSegment] = Field(min_length=1)
    initiatives: list[ChangeInitiative] = Field(default_factory=list)
    issues: list[CultureIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "CulturePortfolioCreate":
        segment_ids = [item.segment_id for item in self.segments]
        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError("Duplicate culture segment IDs are not allowed")
        initiative_ids = [item.initiative_id for item in self.initiatives]
        if len(initiative_ids) != len(set(initiative_ids)):
            raise ValueError("Duplicate change initiative IDs are not allowed")
        issue_ids = [item.issue_id for item in self.issues]
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("Duplicate culture issue IDs are not allowed")
        known = set(segment_ids)
        for item in [*self.initiatives, *self.issues]:
            missing = set(item.affected_segment_ids) - known
            if missing:
                raise ValueError(f"Unknown affected culture segments: {sorted(missing)}")
        return self


class CultureIssueUpdate(BaseModel):
    issue_id: str = Field(min_length=1, max_length=100)
    remediation_progress: float = Field(ge=0, le=100)
    actor_id: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1000)


class CultureAssessment(BaseModel):
    culture_health_score: float = Field(ge=0, le=100)
    change_readiness_score: float = Field(ge=0, le=100)
    leadership_alignment_score: float = Field(ge=0, le=100)
    adoption_risk_score: float = Field(ge=0, le=100)
    fatigue_exposure_score: float = Field(ge=0, le=100)
    vulnerable_segments: list[str] = Field(default_factory=list)
    at_risk_initiatives: list[str] = Field(default_factory=list)
    priority_issues: list[str] = Field(default_factory=list)
    executive_actions: list[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutiveCulturePortfolio(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    executive_owner_id: str
    strategy_portfolio_id: UUID | None = None
    workforce_portfolio_id: UUID | None = None
    transformation_portfolio_id: UUID | None = None
    segments: list[CultureSegment]
    initiatives: list[ChangeInitiative]
    issues: list[CultureIssue]
    assessment: CultureAssessment | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CultureStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    segments: int
    active_initiatives: int
    critical_issues: int
    autonomous_actions_enabled: bool = False


class CultureListResponse(BaseModel):
    items: list[ExecutiveCulturePortfolio]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    resource_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
