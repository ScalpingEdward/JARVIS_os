from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class CommitteeType(str, Enum):
    board = "board"
    audit = "audit"
    risk = "risk"
    compensation = "compensation"
    nomination = "nomination"
    technology = "technology"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class BoardMember(BaseModel):
    member_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    independent: bool = False
    attendance_score: float = Field(ge=0, le=100)
    skill_coverage_score: float = Field(ge=0, le=100)
    challenge_effectiveness_score: float = Field(ge=0, le=100)
    succession_readiness_score: float = Field(ge=0, le=100)


class BoardCommittee(BaseModel):
    committee_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    committee_type: CommitteeType
    member_ids: list[str] = Field(min_length=1)
    charter_coverage_score: float = Field(ge=0, le=100)
    agenda_quality_score: float = Field(ge=0, le=100)
    information_quality_score: float = Field(ge=0, le=100)
    decision_cycle_days: float = Field(ge=0, le=365)
    action_closure_score: float = Field(ge=0, le=100)


class GovernanceIssue(BaseModel):
    issue_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=240)
    severity: Severity
    probability: float = Field(ge=0, le=1)
    impact_score: float = Field(ge=0, le=100)
    committee_id: str | None = None
    remediation_progress: float = Field(default=0, ge=0, le=100)


class BoardPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    executive_owner_id: str = Field(min_length=1, max_length=100)
    strategy_portfolio_id: UUID | None = None
    workforce_portfolio_id: UUID | None = None
    regulatory_portfolio_id: UUID | None = None
    members: list[BoardMember] = Field(min_length=1)
    committees: list[BoardCommittee] = Field(min_length=1)
    issues: list[GovernanceIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "BoardPortfolioCreate":
        member_ids = [item.member_id for item in self.members]
        committee_ids = [item.committee_id for item in self.committees]
        issue_ids = [item.issue_id for item in self.issues]
        if len(member_ids) != len(set(member_ids)):
            raise ValueError("Duplicate board member IDs are not allowed")
        if len(committee_ids) != len(set(committee_ids)):
            raise ValueError("Duplicate committee IDs are not allowed")
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("Duplicate governance issue IDs are not allowed")
        known_members = set(member_ids)
        known_committees = set(committee_ids)
        for committee in self.committees:
            missing = set(committee.member_ids) - known_members
            if missing:
                raise ValueError(f"Unknown board members: {sorted(missing)}")
        for issue in self.issues:
            if issue.committee_id and issue.committee_id not in known_committees:
                raise ValueError(f"Unknown committee: {issue.committee_id}")
        return self


class GovernanceIssueUpdate(BaseModel):
    issue_id: str = Field(min_length=1, max_length=100)
    remediation_progress: float = Field(ge=0, le=100)
    actor_id: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1000)


class BoardAssessment(BaseModel):
    governance_health_score: float = Field(ge=0, le=100)
    independence_score: float = Field(ge=0, le=100)
    skill_coverage_score: float = Field(ge=0, le=100)
    decision_effectiveness_score: float = Field(ge=0, le=100)
    action_closure_score: float = Field(ge=0, le=100)
    succession_readiness_score: float = Field(ge=0, le=100)
    issue_exposure_score: float = Field(ge=0, le=100)
    vulnerable_committees: list[str] = Field(default_factory=list)
    priority_issues: list[str] = Field(default_factory=list)
    executive_actions: list[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutiveBoardPortfolio(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    executive_owner_id: str
    strategy_portfolio_id: UUID | None = None
    workforce_portfolio_id: UUID | None = None
    regulatory_portfolio_id: UUID | None = None
    members: list[BoardMember]
    committees: list[BoardCommittee]
    issues: list[GovernanceIssue]
    assessment: BoardAssessment | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BoardStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    members: int
    committees: int
    open_issues: int
    critical_issues: int
    autonomous_actions_enabled: bool = False


class BoardListResponse(BaseModel):
    items: list[ExecutiveBoardPortfolio]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    resource_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
