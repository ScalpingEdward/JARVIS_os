from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class NodeKind(str, Enum):
    SERVICE = "service"
    MODULE = "module"
    WORKFLOW = "workflow"
    DATASET = "dataset"
    INTEGRATION = "integration"
    USER_SEGMENT = "user-segment"


class DependencyKind(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    DATA = "data"
    CONTROL = "control"
    OBSERVABILITY = "observability"


class Criticality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnalysisState(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    ARCHIVED = "archived"


class GraphNodeCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    node_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=300)
    kind: NodeKind
    criticality: Criticality = Criticality.MEDIUM
    service_key: str | None = Field(default=None, max_length=180)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    discover_external: bool = False

    @model_validator(mode="after")
    def safety(self) -> "GraphNodeCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.discover_external:
            raise ValueError("automatic external dependency discovery is disabled")
        return self


class GraphNodeRecord(GraphNodeCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DependencyCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    source_node_id: UUID
    target_node_id: UUID
    kind: DependencyKind
    propagation_weight: int = Field(default=100, ge=1, le=100)
    description: str = Field(default="", max_length=4000)
    human_approved: bool = True
    execute_change: bool = False

    @model_validator(mode="after")
    def validate_dependency(self) -> "DependencyCreate":
        if self.source_node_id == self.target_node_id:
            raise ValueError("self-dependencies are not allowed")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_change:
            raise ValueError("dependency records never execute changes")
        return self


class DependencyRecord(DependencyCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AnalysisCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    source_node_ids: list[UUID] = Field(min_length=1, max_length=200)
    scenario: str = Field(min_length=1, max_length=500)
    max_depth: int = Field(default=5, ge=1, le=20)
    incident_id: UUID | None = None
    change_id: UUID | None = None
    feature_flag_key: str | None = Field(default=None, max_length=180)
    human_approved: bool = True
    automatic_action: bool = False

    @model_validator(mode="after")
    def safety(self) -> "AnalysisCreate":
        if len(self.source_node_ids) != len(set(self.source_node_ids)):
            raise ValueError("source nodes must be unique")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_action:
            raise ValueError("impact analyses never execute operational actions")
        return self


class ImpactedNode(BaseModel):
    node_id: UUID
    node_key: str
    name: str
    kind: NodeKind
    criticality: Criticality
    depth: int
    impact_score: int = Field(ge=0, le=100)
    path: list[str]


class AnalysisRecord(AnalysisCreate):
    id: UUID = Field(default_factory=uuid4)
    state: AnalysisState = AnalysisState.DRAFT
    impacted_nodes: list[ImpactedNode] = Field(default_factory=list)
    blast_radius_score: int = Field(default=0, ge=0, le=100)
    critical_nodes: int = 0
    high_nodes: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Mutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=4000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "Mutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class MetricsRecord(BaseModel):
    workspace_id: str
    nodes: int
    dependencies: int
    analyses: int
    critical_impacts: int
    average_blast_radius: float


class DependencyImpactStatus(BaseModel):
    version: str = "10.8"
    automatic_discovery: bool = False
    operational_execution: bool = False
    external_scanners: bool = False
    human_approval_required: bool = True
