from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventBusState(str, Enum):
    blocked = "blocked"
    schema_rejected = "schema-rejected"
    duplicate = "duplicate"
    retry_scheduled = "retry-scheduled"
    dead_lettered = "dead-lettered"
    accepted = "accepted"
    dispatched = "dispatched"
    replay_authorized = "replay-authorized"


class RetryClass(str, Enum):
    none = "none"
    transient = "transient"
    rate_limited = "rate-limited"
    dependency_unavailable = "dependency-unavailable"
    permanent = "permanent"


class EventEnvelope(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(min_length=1, max_length=180)
    event_version: int = Field(default=1, ge=1, le=100)
    workspace_id: str = Field(min_length=1, max_length=100)
    producer: str = Field(min_length=1, max_length=120)
    target_module: str = Field(min_length=1, max_length=160)
    correlation_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None
    ordering_key: str | None = Field(default=None, max_length=180)
    sequence_number: int | None = Field(default=None, ge=0)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)
    payload_schema: str = Field(min_length=1, max_length=180)
    payload_schema_version: int = Field(default=1, ge=1, le=100)
    idempotency_key: str = Field(min_length=1, max_length=240)
    replay_of_event_id: UUID | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class EventDeliveryObservation(BaseModel):
    schema_valid: bool = True
    target_registered: bool = True
    dependency_available: bool = True
    consumer_acknowledged: bool = False
    consumer_rejected: bool = False
    timed_out: bool = False
    rate_limited: bool = False
    ordering_violation: bool = False
    attempts: int = Field(default=1, ge=1, le=20)
    latency_ms: int = Field(default=0, ge=0)
    error_code: str | None = Field(default=None, max_length=120)


class EventBusPolicy(BaseModel):
    maximum_attempts: int = Field(default=5, ge=1, le=20)
    maximum_latency_ms: int = Field(default=30_000, gt=0)
    require_schema_validation: bool = True
    require_registered_target: bool = True
    require_correlation_id: bool = True
    require_trace_id: bool = True
    enforce_ordering: bool = True
    allow_replay: bool = False
    require_human_replay_approval: bool = True
    dead_letter_on_permanent_failure: bool = True
    retry_transient_failures: bool = True


class EventBusAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    envelope: EventEnvelope
    observation: EventDeliveryObservation = Field(default_factory=EventDeliveryObservation)
    previous_sequence_number: int | None = Field(default=None, ge=0)
    human_replay_approved: bool = False
    risk_brain_clear: bool = True
    policy: EventBusPolicy = Field(default_factory=EventBusPolicy)


class EventBusScores(BaseModel):
    envelope_integrity: int = Field(ge=0, le=100)
    schema_quality: int = Field(ge=0, le=100)
    traceability: int = Field(ge=0, le=100)
    delivery_reliability: int = Field(ge=0, le=100)
    ordering_safety: int = Field(ge=0, le=100)
    bus_confidence: int = Field(ge=0, le=100)


class EventBusAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    envelope: EventEnvelope
    state: EventBusState
    retry_class: RetryClass
    dispatchable: bool
    replayable: bool
    dead_lettered: bool
    recommended_action: str
    scores: EventBusScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventBusStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    dispatched: int
    dead_letters: int
    latest_state: EventBusState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    event_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
