from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class StakeholderType(str, Enum):
    customer = "customer"
    employee = "employee"
    investor = "investor"
    regulator = "regulator"
    media = "media"
    community = "community"
    partner = "partner"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class StakeholderSegment(BaseModel):
    segment_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    stakeholder_type: StakeholderType
    influence_score: float = Field(ge=0, le=100)
    trust_score: float = Field(ge=0, le=100)
    sentiment_score: float = Field(ge=-100, le=100)
    engagement_score: float = Field(ge=0, le=100)
    narrative_alignment_score: float = Field(ge=0, le=100)
    media_exposure_score: float = Field(ge=0, le=100)


class ReputationIssue(BaseModel):
    issue_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=240)
    severity: Severity
    probability: float = Field(ge=0, le=1)
    velocity_score: float = Field(ge=0, le=100)
    stakeholder_segment_ids: list[str] = Field(default_factory=list)
    remediation_progress: float = Field(default=0, ge=0, le=100)
    response_readiness_score: float = Field(default=0, ge=0, le=100)


class CommunicationChannel(BaseModel):
    channel_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=160)
    reach_score: float = Field(ge=0, le=100)
    credibility_score: float = Field(ge=0, le=100)
    response_speed_score: float = Field(ge=0, le=100)
    monitoring_coverage_score: float = Field(ge=0, le=100)


class ReputationPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    executive_owner_id: str = Field(min_length=1, max_length=100)
    strategy_portfolio_id: UUID | None = None
    culture_portfolio_id: UUID | None = None
    regulatory_portfolio_id: UUID | None = None
    stakeholder_segments: list[StakeholderSegment] = Field(min_length=1)
    issues: list[ReputationIssue] = Field(default_factory=list)
    channels: list[CommunicationChannel] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "ReputationPortfolioCreate":
        segment_ids = [item.segment_id for item in self.stakeholder_segments]
        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError("Duplicate stakeholder segment IDs are not allowed")
        issue_ids = [item.issue_id for item in self.issues]
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("Duplicate reputation issue IDs are not allowed")
        channel_ids = [item.channel_id for item in self.channels]
        if len(channel_ids) != len(set(channel_ids)):
            raise ValueError("Duplicate communication channel IDs are not allowed")
        known_segments = set(segment_ids)
        for issue in self.issues:
            missing = set(issue.stakeholder_segment_ids) - known_segments
            if missing:
                raise ValueError(f"Unknown stakeholder segments: {sorted(missing)}")
        return self


class ReputationIssueUpdate(BaseModel):
    issue_id: str = Field(min_length=1, max_length=100)
    remediation_progress: float = Field(ge=0, le=100)
    response_readiness_score: float | None = Field(default=None, ge=0, le=100)
    actor_id: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1000)


class ReputationAssessment(BaseModel):
    reputation_health_score: float = Field(ge=0, le=100)
    stakeholder_trust_score: float = Field(ge=0, le=100)
    narrative_alignment_score: float = Field(ge=0, le=100)
    issue_exposure_score: float = Field(ge=0, le=100)
    crisis_readiness_score: float = Field(ge=0, le=100)
    vulnerable_segments: list[str] = Field(default_factory=list)
    priority_issues: list[str] = Field(default_factory=list)
    executive_actions: list[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutiveReputationPortfolio(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    executive_owner_id: str
    strategy_portfolio_id: UUID | None = None
    culture_portfolio_id: UUID | None = None
    regulatory_portfolio_id: UUID | None = None
    stakeholder_segments: list[StakeholderSegment]
    issues: list[ReputationIssue]
    channels: list[CommunicationChannel]
    assessment: ReputationAssessment | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReputationStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    stakeholder_segments: int
    open_issues: int
    critical_issues: int
    autonomous_actions_enabled: bool = False


class ReputationListResponse(BaseModel):
    items: list[ExecutiveReputationPortfolio]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    resource_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
