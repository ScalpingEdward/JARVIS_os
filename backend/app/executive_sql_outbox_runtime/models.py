from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SqlOutboxRuntimeState(str, Enum):
    blocked = "blocked"
    migration_required = "migration-required"
    schema_rejected = "schema-rejected"
    relay_unavailable = "relay-unavailable"
    worker_degraded = "worker-degraded"
    runtime_ready = "runtime-ready"
    dispatched = "dispatched"


class RelayMode(str, Enum):
    polling = "polling"
    cdc = "cdc"


class DatabaseType(str, Enum):
    postgresql = "postgresql"
    mysql = "mysql"
    sqlite = "sqlite"


class SqlSchemaObservation(BaseModel):
    migration_present: bool = False
    migration_applied: bool = False
    rollback_verified: bool = False
    outbox_table_exists: bool = False
    inbox_table_exists: bool = False
    checkpoint_table_exists: bool = False
    primary_keys_verified: bool = False
    unique_event_id_index: bool = False
    unique_idempotency_index: bool = False
    unpublished_scan_index: bool = False
    lease_expiry_index: bool = False
    workspace_partition_key: bool = False
    payload_json_validated: bool = False
    raw_secrets_present: bool = False


class RelayWorkerObservation(BaseModel):
    dependency_installed: bool = True
    import_verified: bool = True
    repository_factory_verified: bool = True
    relay_factory_verified: bool = True
    worker_factory_verified: bool = True
    database_connection_verified: bool = False
    cdc_slot_or_binlog_verified: bool = False
    polling_query_verified: bool = False
    skip_locked_verified: bool = False
    lease_claim_verified: bool = False
    heartbeat_verified: bool = False
    broker_publish_verified: bool = False
    checkpoint_commit_verified: bool = False
    graceful_shutdown_verified: bool = False
    health_probe_verified: bool = False
    backlog_records: int = Field(default=0, ge=0)
    oldest_record_age_seconds: int = Field(default=0, ge=0)
    batch_size: int = Field(default=100, ge=1, le=10_000)
    poll_interval_ms: int = Field(default=1_000, ge=50, le=60_000)
    worker_count: int = Field(default=1, ge=1, le=128)
    publish_latency_ms: int = Field(default=0, ge=0)
    consecutive_failures: int = Field(default=0, ge=0)


class SqlOutboxRuntimePolicy(BaseModel):
    allowed_databases: list[DatabaseType] = Field(default_factory=lambda: list(DatabaseType))
    require_migration_and_rollback: bool = True
    require_all_tables: bool = True
    require_integrity_indexes: bool = True
    require_workspace_partitioning: bool = True
    prohibit_raw_secrets: bool = True
    require_skip_locked_for_multi_worker_polling: bool = True
    require_cdc_position_for_cdc: bool = True
    require_lease_and_heartbeat: bool = True
    require_broker_publish_and_checkpoint: bool = True
    require_graceful_shutdown: bool = True
    maximum_backlog_records: int = Field(default=100_000, ge=0)
    maximum_oldest_record_age_seconds: int = Field(default=86_400, ge=1)
    maximum_publish_latency_ms: int = Field(default=20_000, gt=0)
    maximum_consecutive_failures: int = Field(default=5, ge=0)


class SqlOutboxRuntimeAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    transactional_outbox_assessment_id: str = Field(min_length=1, max_length=120)
    transactional_outbox_state: str = Field(min_length=1, max_length=40)
    runtime_id: str = Field(min_length=1, max_length=120)
    database_type: DatabaseType
    schema_version: str = Field(min_length=1, max_length=60)
    relay_mode: RelayMode
    schema_observation: SqlSchemaObservation = Field(default_factory=SqlSchemaObservation)
    worker_observation: RelayWorkerObservation = Field(default_factory=RelayWorkerObservation)
    risk_brain_clear: bool = True
    policy: SqlOutboxRuntimePolicy = Field(default_factory=SqlOutboxRuntimePolicy)


class SqlOutboxRuntimeScores(BaseModel):
    schema_integrity: int = Field(ge=0, le=100)
    migration_safety: int = Field(ge=0, le=100)
    relay_readiness: int = Field(ge=0, le=100)
    worker_resilience: int = Field(ge=0, le=100)
    backlog_health: int = Field(ge=0, le=100)
    runtime_confidence: int = Field(ge=0, le=100)


class SqlOutboxRuntimeAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    runtime_id: str
    database_type: DatabaseType
    schema_version: str
    relay_mode: RelayMode
    state: SqlOutboxRuntimeState
    dispatchable: bool
    target_module: str | None
    recommended_action: str
    scores: SqlOutboxRuntimeScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SqlOutboxRuntimeStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    ready_runtimes: int
    degraded_runtimes: int
    latest_state: SqlOutboxRuntimeState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
