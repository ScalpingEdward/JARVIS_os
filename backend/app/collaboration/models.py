from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AgentRole(StrEnum):
    architect = "architect"
    implementer = "implementer"
    reviewer = "reviewer"
    tester = "tester"
    decision_maker = "decision_maker"


class CollaborationStatus(StrEnum):
    created = "created"
    active = "active"
    reviewing = "reviewing"
    resolved = "resolved"
    escalated = "escalated"


class ContributionStatus(StrEnum):
    proposed = "proposed"
    accepted = "accepted"
    rejected = "rejected"


class Participant(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=50)
    role: AgentRole


class CollaborationCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    objective: str = Field(min_length=5, max_length=5000)
    participants: list[Participant] = Field(min_length=2, max_length=20)
    required_reviews: int = Field(default=1, ge=1, le=10)


class ContributionCreate(BaseModel):
    participant_name: str
    content: str = Field(min_length=1, max_length=20000)
    artifacts: list[str] = Field(default_factory=list)


class ReviewCreate(BaseModel):
    reviewer_name: str
    approved: bool
    comments: str = Field(default="", max_length=10000)


class ContributionRecord(ContributionCreate):
    id: UUID = Field(default_factory=uuid4)
    status: ContributionStatus = ContributionStatus.proposed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewRecord(ReviewCreate):
    id: UUID = Field(default_factory=uuid4)
    contribution_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CollaborationRecord(CollaborationCreate):
    id: UUID = Field(default_factory=uuid4)
    status: CollaborationStatus = CollaborationStatus.created
    contributions: list[ContributionRecord] = Field(default_factory=list)
    reviews: list[ReviewRecord] = Field(default_factory=list)
    selected_contribution_id: UUID | None = None
    conflict_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CollaborationList(BaseModel):
    items: list[CollaborationRecord]
    count: int
