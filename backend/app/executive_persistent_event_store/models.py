from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PersistentEventStoreState(str, Enum):
    blocked = "blocked"
    configuration_required = "configuration-required"
    adapter_unavailable = "adapter-unavailable"
    offset_conflict = "offset-conflict"
    retention_rejected = "retention-rejected"
    store_ready = "store-ready"
    dispatched = "dispatched"


class BrokerType(str, Enum):
    in_memory = "in-memory"
    redis_streams = "redis-streams"
    nats_jetstream = "nats-jetstream"
    kafka = "kafka"
    rabbitmq = "rabbitmq"


class DeliveryGuarantee(str, Enum):
    at_most_once = "at-most-once"
    at_least_once = "at-least-once"
    effectively_once = "effectively-once"


class AckMode(str, Enum):
    automatic = "automatic"
    manual = "manual"
    transactional = "transactional"


class BrokerAdapterObservation(BaseModel):
    dependency_installed: bool = True
    import_verified: bool = True
    adapter_factory_verified: bool = True
    connection_verified: bool = False
    stream_or_topic_exists: bool = False
    persistence_verified: bool = False
    consumer_group_verified: bool = False
    offset_store_verified: bool = False
    idempotent_producer_verified: bool = False
    transactional_commit_verified: bool = False
    encryption_in_transit_verified: bool = True
    authentication_reference_resolved: bool = True
    raw_credentials_present: bool = False
    latency_ms: int = Field(default=0, ge=0)
    replication_factor: int = Field(default=1, ge=1, le=9)


class ConsumerOffsetObservation(BaseModel):
    partition: int = Field(default=0, ge=0)
    committed_offset: int = Field(default=-1, ge=-1)
    observed_offset: int = Field(default=0, ge=0)
    high_watermark: int = Field(default=0, ge=0)
    acknowledgement_persisted: bool = False
    duplicate_delivery_detected: bool = False
    offset_regression_detected: bool = False
    rebalance_in_progress: bool = False


class PersistentEventStorePolicy(BaseModel):
    allowed_brokers: list[BrokerType] = Field(default_factory=lambda: list(BrokerType))
    required_delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.at_least_once
    require_manual_or_transactional_ack: bool = True
    require_persistence: bool = True
    require_consumer_group: bool = True
    require_offset_store: bool = True
    require_idempotent_producer_for_effectively_once: bool = True
    require_transactional_commit_for_effectively_once: bool = True
    require_encryption_in_transit: bool = True
    prohibit_raw_credentials: bool = True
    minimum_replication_factor: int = Field(default=1, ge=1, le=9)
    maximum_latency_ms: int = Field(default=20_000, gt=0)
    retention_hours_minimum: int = Field(default=24, ge=1)
    retention_hours_maximum: int = Field(default=8_760, ge=1)
    allow_compaction: bool = True
    maximum_consumer_lag: int = Field(default=100_000, ge=0)


class PersistentEventStoreAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    event_bus_assessment_id: str = Field(min_length=1, max_length=120)
    event_bus_state: str = Field(min_length=1, max_length=40)
    adapter_id: str = Field(min_length=1, max_length=100)
    broker_type: BrokerType
    stream_name: str = Field(min_length=1, max_length=180)
    consumer_group: str = Field(min_length=1, max_length=180)
    delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.at_least_once
    ack_mode: AckMode = AckMode.manual
    retention_hours: int = Field(default=168, ge=1)
    compaction_enabled: bool = False
    observation: BrokerAdapterObservation = Field(default_factory=BrokerAdapterObservation)
    offset: ConsumerOffsetObservation = Field(default_factory=ConsumerOffsetObservation)
    risk_brain_clear: bool = True
    policy: PersistentEventStorePolicy = Field(default_factory=PersistentEventStorePolicy)


class PersistentEventStoreScores(BaseModel):
    adapter_readiness: int = Field(ge=0, le=100)
    persistence_integrity: int = Field(ge=0, le=100)
    delivery_safety: int = Field(ge=0, le=100)
    offset_integrity: int = Field(ge=0, le=100)
    security_quality: int = Field(ge=0, le=100)
    store_confidence: int = Field(ge=0, le=100)


class PersistentEventStoreAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    event_bus_assessment_id: str
    adapter_id: str
    broker_type: BrokerType
    stream_name: str
    consumer_group: str
    state: PersistentEventStoreState
    dispatchable: bool
    target_module: str | None
    consumer_lag: int
    recommended_action: str
    scores: PersistentEventStoreScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PersistentEventStoreStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    ready_stores: int
    offset_conflicts: int
    latest_state: PersistentEventStoreState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
