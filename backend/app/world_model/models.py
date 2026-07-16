from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EntityKind(str, Enum):
    market = "market"
    trading_setup = "trading_setup"
    project = "project"
    mission = "mission"
    agent = "agent"
    connector = "connector"
    calendar_event = "calendar_event"
    research_event = "research_event"
    decision = "decision"
    goal = "goal"
    resource = "resource"
    blocker = "blocker"


class RelationKind(str, Enum):
    depends_on = "depends_on"
    blocks = "blocks"
    affects = "affects"
    assigned_to = "assigned_to"
    sourced_from = "sourced_from"
    supports = "supports"
    conflicts_with = "conflicts_with"
    triggers = "triggers"


class EntityState(str, Enum):
    active = "active"
    watch = "watch"
    degraded = "degraded"
    blocked = "blocked"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    archived = "archived"


class WorldEntityCreate(BaseModel):
    kind: EntityKind
    external_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    state: EntityState = EntityState.active
    priority: int = Field(default=3, ge=1, le=5)
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class WorldEntity(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    kind: EntityKind
    external_id: str
    name: str
    state: EntityState
    priority: int
    attributes: dict[str, str | int | float | bool | None]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RelationCreate(BaseModel):
    source_id: UUID
    target_id: UUID
    kind: RelationKind
    strength: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str | None = Field(default=None, max_length=500)


class WorldRelation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    target_id: UUID
    kind: RelationKind
    strength: float
    reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorldEventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=120)
    entity_id: UUID
    severity: int = Field(default=3, ge=1, le=5)
    summary: str = Field(min_length=1, max_length=1000)
    data: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class WorldEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    event_type: str
    entity_id: UUID
    severity: int
    summary: str
    data: dict[str, str | int | float | bool | None]
    consequences: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorldSnapshot(BaseModel):
    entities: int
    relations: int
    events: int
    active: int
    blocked: int
    degraded: int
    high_priority: int
    automatic_order_execution: bool = False
    automatic_merge: bool = False
