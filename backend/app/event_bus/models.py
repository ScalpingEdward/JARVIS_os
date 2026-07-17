from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class TopicState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"


class DeliveryMode(str, Enum):
    AT_MOST_ONCE = "at-most-once"
    AT_LEAST_ONCE = "at-least-once"
    EXACTLY_ONCE_PLAN = "exactly-once-plan"


class EventState(str, Enum):
    PUBLISHED = "published"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    DEAD_LETTER = "dead-letter"
    REPLAY_PLANNED = "replay-planned"
    REPLAYED = "replayed"


class SubscriptionState(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class TopicCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    topic_key: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9*_.-]+$")
    description: str = Field(default="", max_length=4000)
    critical_event_types: list[str] = Field(default_factory=list, max_length=500)
    retention_hours: int = Field(default=168, ge=1, le=87600)
    human_approved: bool = True
    external_broker: bool = False
    automatic_activation: bool = False

    @model_validator(mode="after")
    def safety(self) -> "TopicCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.external_broker:
            raise ValueError("external event brokers are disabled in v9.7")
        if self.automatic_activation:
            raise ValueError("automatic topic activation is disabled")
        return self


class TopicRecord(TopicCreate):
    id: UUID = Field(default_factory=uuid4)
    state: TopicState = TopicState.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SubscriptionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    topic_id: UUID
    subscriber_module: str = Field(min_length=1, max_length=160)
    event_types: list[str] = Field(default_factory=list, max_length=500)
    filter_fields: dict[str, str | int | float | bool] = Field(default_factory=dict)
    delivery_mode: DeliveryMode = DeliveryMode.AT_LEAST_ONCE
    max_retries: int = Field(default=3, ge=0, le=20)
    backoff_seconds: int = Field(default=5, ge=0, le=86400)
    human_approved: bool = True
    execute_handler: bool = False

    @model_validator(mode="after")
    def safety(self) -> "SubscriptionCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_handler:
            raise ValueError("subscriptions do not execute external handlers in v9.7")
        return self


class SubscriptionRecord(SubscriptionCreate):
    id: UUID = Field(default_factory=uuid4)
    state: SubscriptionState = SubscriptionState.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventPublish(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    publisher_id: str = Field(min_length=1, max_length=120)
    source_module: str = Field(min_length=1, max_length=160)
    source_version: str = Field(default="unknown", max_length=80)
    topic_id: UUID
    event_type: str = Field(min_length=1, max_length=240)
    priority: Priority = Priority.NORMAL
    correlation_id: str = Field(min_length=1, max_length=240)
    causation_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    execute_action: bool = False
    publish_external: bool = False

    @model_validator(mode="after")
    def safety(self) -> "EventPublish":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_action:
            raise ValueError("event publication never executes operational actions")
        if self.publish_external:
            raise ValueError("external event publication is disabled")
        return self


class EventRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    publisher_id: str
    source_module: str
    source_version: str
    topic_id: UUID
    event_type: str
    priority: Priority
    correlation_id: str
    causation_id: UUID | None = None
    payload: dict[str, Any]
    metadata: dict[str, Any]
    state: EventState = EventState.PUBLISHED
    matching_subscription_ids: list[UUID] = Field(default_factory=list)
    retry_count: int = 0
    failure_reason: str | None = None
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeliveryMutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    success: bool
    reason: str = Field(default="", max_length=3000)
    human_approved: bool = True

    @model_validator(mode="after")
    def safety(self) -> "DeliveryMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class ReplayRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    event_ids: list[UUID] = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=3000)
    human_approved: bool = True
    automatic_replay: bool = False
    execute_subscribers: bool = False

    @model_validator(mode="after")
    def safety(self) -> "ReplayRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_replay:
            raise ValueError("automatic replay is disabled")
        if self.execute_subscribers:
            raise ValueError("replay is planning-only in v9.7")
        return self


class ReplayRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    requester_id: str
    source_event_ids: list[UUID]
    replay_event_ids: list[UUID] = Field(default_factory=list)
    reason: str
    state: str = "planned"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsRecord(BaseModel):
    workspace_id: str
    topics: int
    subscriptions: int
    events: int
    published: int
    acknowledged: int
    failed: int
    dead_letter: int
    replay_plans: int
    retries: int
    queue_length: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    entity_type: str
    entity_id: UUID | None = None
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventBusStatus(BaseModel):
    version: str = "9.7"
    topics: int
    subscriptions: int
    events: int
    dead_letter_events: int
    replay_plans: int
    external_broker_enabled: bool = False
    automatic_replay_enabled: bool = False
    executes_actions: bool = False
