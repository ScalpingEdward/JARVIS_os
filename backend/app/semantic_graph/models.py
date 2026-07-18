from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class EntityType(str, Enum):
    SERVICE = "service"
    ASSET = "asset"
    AGENT = "agent"
    WORKFLOW = "workflow"
    PLAYBOOK = "playbook"
    MISSION = "mission"
    USER = "user"
    DOCUMENT = "document"
    BROKER = "broker"
    STRATEGY = "strategy"
    INCIDENT = "incident"
    MODULE = "module"
    CUSTOM = "custom"


class EntityState(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class RelationshipType(str, Enum):
    DEPENDS_ON = "depends_on"
    USES = "uses"
    PRODUCES = "produces"
    OWNS = "owns"
    DESCRIBES = "describes"
    MONITORS = "monitors"
    AFFECTS = "affects"
    EXECUTES = "executes"
    REFERENCES = "references"
    RELATED_TO = "related_to"


class GraphEntityCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    key: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_.:-]+$")
    entity_type: EntityType
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=10_000)
    aliases: list[str] = Field(default_factory=list, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=100)
    source_refs: list[str] = Field(default_factory=list, max_length=100)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    attributes: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "GraphEntityCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_external_action:
            raise ValueError("automatic external actions are disabled")
        return self


class GraphEntityRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    key: str
    entity_type: EntityType
    name: str
    description: str
    aliases: list[str]
    tags: list[str]
    source_refs: list[str]
    confidence: float
    attributes: dict[str, Any]
    state: EntityState = EntityState.ACTIVE
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RelationshipCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: RelationshipType
    label: str = Field(default="", max_length=300)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_refs: list[str] = Field(default_factory=list, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)
    bidirectional: bool = False
    human_approved: bool = True
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "RelationshipCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_external_action:
            raise ValueError("automatic external actions are disabled")
        if self.source_entity_id == self.target_entity_id:
            raise ValueError("self relationships are not allowed")
        return self


class RelationshipRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: RelationshipType
    label: str
    confidence: float
    source_refs: list[str]
    metadata: dict[str, Any]
    bidirectional: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GraphSearchRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=1, max_length=1000)
    entity_types: list[EntityType] = Field(default_factory=list, max_length=20)
    minimum_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    include_archived: bool = False
    limit: int = Field(default=20, ge=1, le=100)


class GraphSearchHit(BaseModel):
    entity: GraphEntityRecord
    score: float
    matched_fields: list[str]


class TraversalRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    start_entity_id: UUID
    relationship_types: list[RelationshipType] = Field(default_factory=list, max_length=20)
    max_depth: int = Field(default=3, ge=1, le=8)
    direction: str = Field(default="both", pattern=r"^(outgoing|incoming|both)$")


class GraphPath(BaseModel):
    entity_ids: list[UUID]
    relationship_ids: list[UUID]
    depth: int
    confidence: float


class ImpactResult(BaseModel):
    root_entity: GraphEntityRecord
    affected_entities: list[GraphEntityRecord]
    paths: list[GraphPath]
    impact_count: int
    max_depth: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    target_type: str
    target_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeGraphStatus(BaseModel):
    service: str = "semantic-graph"
    version: str = "14.0"
    entities: int
    relationships: int
    active_entities: int
    archived_entities: int
    entity_types: int
    relationship_types: int
    semantic_search_enabled: bool = True
    impact_analysis_enabled: bool = True
    external_execution_enabled: bool = False
    workspace_isolation: bool = True
    audit_enabled: bool = True
