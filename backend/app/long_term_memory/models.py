from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    episodic = "episodic"
    semantic = "semantic"
    trading = "trading"
    relationship = "relationship"
    goal = "goal"
    experience = "experience"
    preference = "preference"
    project = "project"
    business = "business"


class MemorySource(str, Enum):
    human = "human"
    agent = "agent"
    mission = "mission"
    trading = "trading"
    connector = "connector"
    system = "system"


class MemoryCreate(BaseModel):
    memory_type: MemoryType
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=20000)
    source: MemorySource = MemorySource.human
    source_ref: str | None = Field(default=None, max_length=500)
    tags: set[str] = Field(default_factory=set)
    entities: set[str] = Field(default_factory=set)
    importance: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.7, ge=0, le=1)
    occurred_at: datetime | None = None
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class MemoryRecord(MemoryCreate):
    id: UUID = Field(default_factory=uuid4)
    version: int = 1
    supersedes_id: UUID | None = None
    archived: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=20000)
    importance: float | None = Field(default=None, ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    tags: set[str] | None = None
    entities: set[str] | None = None
    archived: bool | None = None
    reason: str = Field(min_length=1, max_length=500)


class RelationshipType(str, Enum):
    caused = "caused"
    resulted_in = "resulted_in"
    related_to = "related_to"
    supports = "supports"
    contradicts = "contradicts"
    learned_from = "learned_from"
    applies_to = "applies_to"
    prefers = "prefers"


class MemoryRelationshipCreate(BaseModel):
    source_memory_id: UUID
    target_memory_id: UUID
    relationship: RelationshipType
    strength: float = Field(default=0.5, ge=0, le=1)
    note: str | None = Field(default=None, max_length=1000)


class MemoryRelationshipRecord(MemoryRelationshipCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TradingOutcome(str, Enum):
    win = "win"
    loss = "loss"
    breakeven = "breakeven"
    skipped = "skipped"


class TradingMemoryCreate(BaseModel):
    instrument: str = Field(min_length=1, max_length=40)
    setup: str = Field(min_length=1, max_length=160)
    session: str = Field(min_length=1, max_length=80)
    timeframe: str = Field(min_length=1, max_length=20)
    outcome: TradingOutcome
    pnl_r: float | None = None
    mfe_r: float | None = None
    mae_r: float | None = None
    conditions: set[str] = Field(default_factory=set)
    mistakes: set[str] = Field(default_factory=set)
    lessons: str | None = Field(default=None, max_length=4000)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConsolidationRequest(BaseModel):
    minimum_similarity: float = Field(default=0.8, ge=0.5, le=1)
    archive_duplicates: bool = True
    actor: str = Field(default="system", min_length=1, max_length=120)


class ConsolidationResult(BaseModel):
    reviewed: int
    clusters: int
    archived: int
    generated_experiences: int


class MemoryAuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    memory_id: UUID | None = None
    action: str
    actor: str
    details: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryStatus(BaseModel):
    total: int
    active: int
    archived: int
    relationships: int
    trading_memories: int
    versions: int
    automatic_order_execution: bool = False
    automatic_merge: bool = False
