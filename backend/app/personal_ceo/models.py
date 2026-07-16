from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ExecutiveDomain(str, Enum):
    trading = "trading"
    business = "business"
    engineering = "engineering"
    research = "research"
    finance = "finance"
    health = "health"
    personal = "personal"
    legal = "legal"
    operations = "operations"


class Urgency(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    critical = "critical"


class ItemState(str, Enum):
    ready = "ready"
    blocked = "blocked"
    waiting_approval = "waiting_approval"
    monitoring = "monitoring"
    completed = "completed"


class ExecutiveItem(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    domain: ExecutiveDomain
    urgency: Urgency = Urgency.normal
    state: ItemState = ItemState.ready
    impact: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)
    deadline_at: datetime | None = None
    requires_approval: bool = False
    source: str = Field(default="manual", max_length=120)
    rationale: str = Field(default="", max_length=1200)
    next_action: str = Field(default="", max_length=600)


class ExecutiveBriefingCreate(BaseModel):
    items: list[ExecutiveItem] = Field(default_factory=list, max_length=200)
    energy_level: float | None = Field(default=None, ge=0, le=1)
    available_minutes: int | None = Field(default=None, ge=0, le=1440)
    notes: list[str] = Field(default_factory=list, max_length=50)


class RankedExecutiveItem(ExecutiveItem):
    priority_score: float = Field(ge=0, le=1)
    priority_reason: str


class ExecutiveBriefing(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    salutation: str = "MASTER Brano"
    headline: str
    daily_focus: str
    top_priorities: list[RankedExecutiveItem]
    risks: list[str]
    approvals: list[str]
    monitoring: list[str]
    recommendations: list[str]
    deferred_count: int = 0
    confidence: float = Field(default=0, ge=0, le=1)
    automatic_execution: bool = False
    automatic_order_execution: bool = False


class PersonalCEOProfile(BaseModel):
    owner_name: str = "Branislav Gombos"
    preferred_salutation: str = "MASTER Brano"
    assistant_name: str = "PHOENIX"
    timezone: str = "Europe/Berlin"
    max_daily_priorities: int = Field(default=5, ge=1, le=20)
    trading_requires_approval: bool = True
    critical_actions_require_approval: bool = True


class PersonalCEOStatus(BaseModel):
    profile: PersonalCEOProfile
    briefings: int
    latest_briefing_at: datetime | None = None
    automatic_execution: bool = False
    automatic_order_execution: bool = False
    human_approval_required: bool = True
