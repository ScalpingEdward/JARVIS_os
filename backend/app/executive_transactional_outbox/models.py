from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TransactionalOutboxState(str, Enum):
    blocked = "blocked"
    transaction_required = "transaction-required"
    duplicate = "duplicate"
    lease_conflict = "lease-conflict"
    recovery_required = "recovery-required"
    checkpoint_ready = "checkpoint-ready"
    dispatched = "dispatched"


class OutboxObservation(BaseModel):
    business_commit_succeeded: bool = False
    outbox_inserted_same_transaction: bool = False
    transaction_id_verified: bool = False
    event_persisted: bool = False
    publisher_lease_acquired: bool = False
    lease_owner_verified: bool = False
    lease_expired: bool = False
    publish_attempted: bool = False
    broker_acknowledged: bool = False
    published_marker_persisted: bool = False
    checkpoint_persisted: bool = False
    inbox_record_persisted: bool = False
    inbox_duplicate_detected: bool = False
    consumer_side_effect_committed: bool = False
    consumer_ack_persisted: bool = False
    recovery_scan_completed: bool = False
    raw_transaction_payload_present: bool = False
    publish_attempts: int = Field(default=0, ge=0, le=20)
    age_seconds: int = Field(default=0, ge=0)
    lease_age_seconds: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    error_code: str | None = Field(default=None, max_length=120)


class TransactionalOutboxPolicy(BaseModel):
    maximum_publish_attempts: int = Field(default=5, ge=1, le=20)
    maximum_record_age_seconds: int = Field(default=86_400, ge=1)
    maximum_lease_age_seconds: int = Field(default=300, ge=1)
    maximum_latency_ms: int = Field(default=20_000, gt=0)
    require_same_transaction_write: bool = True
    require_transaction_id_verification: bool = True
    require_publisher_lease: bool = True
    require_broker_ack_before_mark_published: bool = True
    require_checkpoint_persistence: bool = True
    require_inbox_deduplication: bool = True
    require_consumer_atomicity: bool = True
    allow_expired_lease_recovery: bool = True
    prohibit_raw_transaction_payload: bool = True


class TransactionalOutboxAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    persistent_store_assessment_id: str = Field(min_length=1, max_length=120)
    persistent_store_state: str = Field(min_length=1, max_length=40)
    outbox_record_id: UUID = Field(default_factory=uuid4)
    event_id: UUID = Field(default_factory=uuid4)
    transaction_id: str = Field(min_length=1, max_length=180)
    aggregate_id: str = Field(min_length=1, max_length=180)
    publisher_id: str = Field(min_length=1, max_length=120)
    consumer_id: str = Field(min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=1, max_length=240)
    checkpoint_key: str = Field(min_length=1, max_length=240)
    observation: OutboxObservation = Field(default_factory=OutboxObservation)
    risk_brain_clear: bool = True
    policy: TransactionalOutboxPolicy = Field(default_factory=TransactionalOutboxPolicy)


class TransactionalOutboxScores(BaseModel):
    transaction_integrity: int = Field(ge=0, le=100)
    publication_safety: int = Field(ge=0, le=100)
    inbox_integrity: int = Field(ge=0, le=100)
    recovery_readiness: int = Field(ge=0, le=100)
    checkpoint_quality: int = Field(ge=0, le=100)
    outbox_confidence: int = Field(ge=0, le=100)


class TransactionalOutboxAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    outbox_record_id: UUID
    event_id: UUID
    transaction_id: str
    aggregate_id: str
    publisher_id: str
    consumer_id: str
    state: TransactionalOutboxState
    dispatchable: bool
    recoverable: bool
    target_module: str | None
    recommended_action: str
    scores: TransactionalOutboxScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TransactionalOutboxStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    dispatched: int
    recovery_required: int
    latest_state: TransactionalOutboxState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    event_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
