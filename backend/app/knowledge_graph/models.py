from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class NodeKind(str, Enum):
    person = "person"
    company = "company"
    market = "market"
    asset = "asset"
    strategy = "strategy"
    setup = "setup"
    session = "session"
    project = "project"
    agent = "agent"
    connector = "connector"
    event = "event"
    concept = "concept"
    document = "document"
    goal = "goal"


class EdgeKind(str, Enum):
    related_to = "related_to"
    depends_on = "depends_on"
    causes = "causes"
    affects = "affects"
    supports = "supports"
    contradicts = "contradicts"
    prefers = "prefers"
    uses = "uses"
    owns = "owns"
    part_of = "part_of"
    similar_to = "similar_to"
    benefits_from = "benefits_from"
    supplied_by = "supplied_by"
    triggers = "triggers"


class NodeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: NodeKind
    aliases: list[str] = Field(default_factory=list)
    tags: set[str] = Field(default_factory=set)
    properties: dict[str, str | int | float | bool] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)


class NodeRecord(NodeCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EdgeCreate(BaseModel):
    source_id: UUID
    target_id: UUID
    kind: EdgeKind
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    properties: dict[str, str | int | float | bool] = Field(default_factory=dict)


class EdgeRecord(EdgeCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GraphPath(BaseModel):
    node_ids: list[UUID]
    edge_ids: list[UUID]
    total_weight: float


class GraphReasonRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    start_node_ids: list[UUID] = Field(default_factory=list)
    max_depth: int = Field(default=3, ge=1, le=6)


class GraphReasonResponse(BaseModel):
    answer: str
    supporting_paths: list[GraphPath]
    confidence: float = Field(ge=0.0, le=1.0)
    limitations: list[str] = Field(default_factory=list)
    advisory_only: bool = True


class GraphStatus(BaseModel):
    nodes: int
    edges: int
    node_kinds: dict[str, int]
    edge_kinds: dict[str, int]
    automatic_order_execution: bool = False
    automatic_merge: bool = False
