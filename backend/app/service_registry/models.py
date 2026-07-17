from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ServiceState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class DependencyKind(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    EVENT = "event"
    DATA = "data"


class CompatibilityState(str, Enum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


class ServiceCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    service_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=240)
    version: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=100)
    api_routes: list[str] = Field(default_factory=list, max_length=500)
    produces_events: list[str] = Field(default_factory=list, max_length=500)
    consumes_events: list[str] = Field(default_factory=list, max_length=500)
    permissions: list[str] = Field(default_factory=list, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_activation: bool = False
    external_discovery: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "ServiceCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_activation:
            raise ValueError("automatic service activation is disabled")
        if self.external_discovery:
            raise ValueError("automatic external service discovery is disabled")
        return self


class ServiceRecord(ServiceCreate):
    id: UUID = Field(default_factory=uuid4)
    state: ServiceState = ServiceState.DRAFT
    health: HealthState = HealthState.UNKNOWN
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DependencyCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    source_service_id: UUID
    target_service_id: UUID
    kind: DependencyKind = DependencyKind.REQUIRED
    minimum_version: str | None = Field(default=None, max_length=80)
    maximum_version: str | None = Field(default=None, max_length=80)
    description: str = Field(default="", max_length=2000)
    human_approved: bool = True
    automatic_rewire: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "DependencyCreate":
        if self.source_service_id == self.target_service_id:
            raise ValueError("a service cannot depend on itself")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_rewire:
            raise ValueError("automatic dependency changes are disabled")
        return self


class DependencyRecord(DependencyCreate):
    id: UUID = Field(default_factory=uuid4)
    compatibility: CompatibilityState = CompatibilityState.UNKNOWN
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HealthUpdate(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    state: HealthState
    reason: str = Field(default="", max_length=2000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "HealthUpdate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class Mutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=2000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "Mutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class ImpactRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    service_id: UUID
    proposed_version: str | None = Field(default=None, max_length=80)
    changed_routes: list[str] = Field(default_factory=list, max_length=500)
    changed_events: list[str] = Field(default_factory=list, max_length=500)
    include_optional: bool = True
    execute_changes: bool = False

    @model_validator(mode="after")
    def planning_only(self) -> "ImpactRequest":
        if self.execute_changes:
            raise ValueError("impact analysis is planning-only and never executes changes")
        return self


class GraphRecord(BaseModel):
    workspace_id: str
    nodes: list[ServiceRecord]
    edges: list[DependencyRecord]
    cycles: list[list[UUID]] = Field(default_factory=list)


class ImpactRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    service_id: UUID
    affected_service_ids: list[UUID] = Field(default_factory=list)
    affected_routes: list[str] = Field(default_factory=list)
    affected_events: list[str] = Field(default_factory=list)
    incompatible_dependencies: list[UUID] = Field(default_factory=list)
    risk_score: int = Field(default=0, ge=0, le=100)
    requires_review: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    entity_type: str
    entity_id: UUID | None = None
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RegistryStatus(BaseModel):
    version: str = "9.6"
    services: int
    dependencies: int
    impacts: int
    cycles_detected: int
    automatic_activation_enabled: bool = False
    automatic_rewire_enabled: bool = False
    external_discovery_enabled: bool = False
    executes_actions: bool = False
