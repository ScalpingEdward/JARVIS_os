from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PageState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class ComponentStatus(str, Enum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial-outage"
    MAJOR_OUTAGE = "major-outage"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class MessageKind(str, Enum):
    INCIDENT = "incident"
    MAINTENANCE = "maintenance"
    INFORMATION = "information"
    RECOVERY = "recovery"


class MessageState(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


class AudienceType(str, Enum):
    INTERNAL = "internal"
    CUSTOMER = "customer"
    PARTNER = "partner"
    EXECUTIVE = "executive"
    CUSTOM = "custom"


class ComponentCreate(BaseModel):
    component_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=300)
    service_key: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=3000)
    display_order: int = Field(default=0, ge=0, le=10000)
    initial_status: ComponentStatus = ComponentStatus.OPERATIONAL


class StatusPageCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    page_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=6000)
    timezone_name: str = Field(default="UTC", min_length=1, max_length=120)
    components: list[ComponentCreate] = Field(min_length=1, max_length=500)
    default_audiences: list[AudienceType] = Field(default_factory=lambda: [AudienceType.INTERNAL])
    labels: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_activation: bool = False
    automatic_publish: bool = False
    notify_external: bool = False
    external_provider: bool = False

    @model_validator(mode="after")
    def validate_page(self) -> "StatusPageCreate":
        keys = [item.component_key for item in self.components]
        if len(keys) != len(set(keys)):
            raise ValueError("component keys must be unique")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_activation:
            raise ValueError("automatic status-page activation is disabled")
        if self.automatic_publish:
            raise ValueError("automatic status publication is disabled")
        if self.notify_external:
            raise ValueError("automatic external stakeholder notification is disabled")
        if self.external_provider:
            raise ValueError("external status-page providers are disabled")
        return self


class ComponentRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    component_key: str
    name: str
    service_key: str
    description: str = ""
    display_order: int = 0
    status: ComponentStatus = ComponentStatus.OPERATIONAL
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusPageRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    page_key: str
    name: str
    description: str = ""
    timezone_name: str = "UTC"
    components: list[ComponentRecord]
    default_audiences: list[AudienceType]
    labels: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    state: PageState = PageState.DRAFT
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


class ComponentStatusUpdate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    page_id: UUID
    component_id: UUID
    status: ComponentStatus
    reason: str = Field(default="", max_length=4000)
    related_incident_id: UUID | None = None
    human_approved: bool = True
    execute_change: bool = False

    @model_validator(mode="after")
    def safety(self) -> "ComponentStatusUpdate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_change:
            raise ValueError("component status records never execute service changes")
        return self


class CommunicationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    page_id: UUID
    message_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    kind: MessageKind
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=12000)
    audiences: list[AudienceType] = Field(min_length=1, max_length=20)
    custom_audience_keys: list[str] = Field(default_factory=list, max_length=200)
    affected_component_ids: list[UUID] = Field(default_factory=list, max_length=500)
    related_incident_id: UUID | None = None
    related_change_id: UUID | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    required_approvals: int = Field(default=1, ge=1, le=20)
    human_approved: bool = True
    automatic_publish: bool = False
    notify_external: bool = False

    @model_validator(mode="after")
    def validate_message(self) -> "CommunicationCreate":
        if self.scheduled_start and self.scheduled_end and self.scheduled_end <= self.scheduled_start:
            raise ValueError("scheduled_end must be after scheduled_start")
        if AudienceType.CUSTOM in self.audiences and not self.custom_audience_keys:
            raise ValueError("custom audiences require custom_audience_keys")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_publish:
            raise ValueError("automatic status publication is disabled")
        if self.notify_external:
            raise ValueError("automatic external stakeholder notification is disabled")
        return self


class CommunicationRecord(CommunicationCreate):
    id: UUID = Field(default_factory=uuid4)
    state: MessageState = MessageState.DRAFT
    approval_count: int = 0
    published_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    communication_id: UUID
    comment: str = Field(default="", max_length=4000)
    human_approved: bool = True
    automatic_decision: bool = False

    @model_validator(mode="after")
    def safety(self) -> "ApprovalCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_decision:
            raise ValueError("automatic communication approvals are disabled")
        return self


class ApprovalRecord(ApprovalCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsRecord(BaseModel):
    workspace_id: str
    pages: int
    active_pages: int
    components: int
    degraded_components: int
    outage_components: int
    draft_messages: int
    review_messages: int
    published_messages: int
    maintenance_messages: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    entity_type: str
    entity_id: UUID | None = None
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCommunicationStatus(BaseModel):
    version: str = "10.6"
    pages: int
    components: int
    communications: int
    published_messages: int
    automatic_activation_enabled: bool = False
    automatic_publication_enabled: bool = False
    external_notifications_enabled: bool = False
    external_provider_enabled: bool = False
