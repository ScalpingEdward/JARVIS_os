from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class SourceType(str, Enum):
    news = "news"
    central_bank = "central_bank"
    regulator = "regulator"
    company = "company"
    social = "social"
    telegram = "telegram"
    github = "github"
    research = "research"
    economic_calendar = "economic_calendar"
    document = "document"


class EventState(str, Enum):
    new = "new"
    verified = "verified"
    disputed = "disputed"
    duplicate = "duplicate"
    archived = "archived"


class ImpactDomain(str, Enum):
    market = "market"
    project = "project"
    company = "company"
    operations = "operations"
    technology = "technology"


class ResearchSource(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    source_type: SourceType
    url: HttpUrl | None = None
    credibility: float = Field(default=0.5, ge=0, le=1)
    primary_source: bool = False


class ImpactAssessment(BaseModel):
    domain: ImpactDomain
    target: str = Field(min_length=1, max_length=180)
    direction: float = Field(default=0, ge=-1, le=1)
    magnitude: float = Field(default=0, ge=0, le=1)
    horizon: str = Field(default="unknown", max_length=80)
    rationale: str = Field(default="", max_length=1200)


class ResearchEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=5000)
    source: ResearchSource
    published_at: datetime | None = None
    entities: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    impacts: list[ImpactAssessment] = Field(default_factory=list)
    relevance: float = Field(default=0.5, ge=0, le=1)


class ResearchEvent(ResearchEventCreate):
    id: UUID = Field(default_factory=uuid4)
    state: EventState = EventState.new
    confidence: float = Field(default=0, ge=0, le=1)
    contradiction_ids: list[UUID] = Field(default_factory=list)
    duplicate_of: UUID | None = None
    graph_links: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResearchEventList(BaseModel):
    items: list[ResearchEvent]
    count: int


class ResearchBrief(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_ids: list[UUID]
    headline: str
    summary: str
    key_entities: list[str]
    opportunities: list[str]
    risks: list[str]
    contradictions: list[str]
    confidence: float = Field(ge=0, le=1)


class ResearchStatus(BaseModel):
    total_events: int
    verified: int
    disputed: int
    duplicates: int
    high_relevance: int
    sources: int
    automatic_order_execution: bool = False
    automatic_merge: bool = False
