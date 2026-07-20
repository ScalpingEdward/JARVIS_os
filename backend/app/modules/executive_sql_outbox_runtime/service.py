from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    RelayMode,
    SqlOutboxRuntimeAssessment,
    SqlOutboxRuntimeAssessmentCreate,
    SqlOutboxRuntimeScores,
    SqlOutboxRuntimeState,
    SqlOutboxRuntimeStatusResponse,
)


class ExecutiveSqlOutboxRuntimeService:
    def __init__(self) -> None:
        self._records: dict[UUID, SqlOutboxRuntimeAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._runtime_versions: set[tuple[str, str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: SqlOutboxRuntimeAssessmentCreate) -> SqlOutboxRuntimeAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        runtime_key = (payload.workspace_id, payload.runtime_id, payload.schema_version)
        if source_key in self._source_keys:
            raise ValueError("Duplicate SQL outbox runtime source key")
        if runtime_key in self._runtime_versions:
            raise ValueError("Duplicate SQL outbox runtime schema version")

        schema = payload.schema_observation
        worker = payload.worker_observation
        policy = payload.policy
        reasons: list[str] = []

        migration_safe = schema.migration_present and schema.migration_applied and schema.rollback_verified
        tables_safe = schema.outbox_table_exists and schema.inbox_table_exists and schema.checkpoint_table_exists
        indexes_safe = (
            schema.primary_keys_verified
            and schema.unique_event_id_index
            and schema.unique_idempotency_index
            and schema.unpublished_scan_index
            and schema.lease_expiry_index
        )
        schema_safe = (
            migration_safe
            and tables_safe
            and indexes_safe
            and schema.workspace_partition_key
            and schema.payload_json_validated
            and not schema.raw_secrets_present
        )
        dependency_ready = worker.dependency_installed and worker.import_verified
        factory_ready = worker.repository_factory_verified and worker.relay_factory_verified and worker.worker_factory_verified
        relay_ready = worker.database_connection_verified and (
            worker.cdc_slot_or_binlog_verified if payload.relay_mode == RelayMode.cdc else worker.polling_query_verified
        )
        concurrency_safe = not (
            payload.relay_mode == RelayMode.polling
            and worker.worker_count > 1
            and policy.require_skip_locked_for_multi_worker_polling
            and not worker.skip_locked_verified
        )
        recovery_safe = worker.lease_claim_verified and worker.heartbeat_verified
        publication_safe = worker.broker_publish_verified and worker.checkpoint_commit_verified
        lifecycle_safe = worker.graceful_shutdown_verified and worker.health_probe_verified
        backlog_safe = (
            worker.backlog_records <= policy.maximum_backlog_records
            and worker.oldest_record_age_seconds <= policy.maximum_oldest_record_age_seconds
            and worker.publish_latency_ms <= policy.maximum_publish_latency_ms
            and worker.consecutive_failures <= policy.maximum_consecutive_failures
        )

        if not payload.risk_brain_clear:
            state, action = SqlOutboxRuntimeState.blocked, "block-sql-outbox-runtime"
            reasons.append("Risk Brain blocks SQL outbox runtime preparation")
        elif payload.transactional_outbox_state not in {"checkpoint-ready", "dispatched"}:
            state, action = SqlOutboxRuntimeState.blocked, "complete-transactional-outbox-governance"
            reasons.append("Transactional outbox governance has not authorized runtime preparation")
        elif payload.database_type not in policy.allowed_databases:
            state, action = SqlOutboxRuntimeState.schema_rejected, "select-approved-database"
            reasons.append("Database type is not allowed")
        elif policy.prohibit_raw_secrets and schema.raw_secrets_present:
            state, action = SqlOutboxRuntimeState.blocked, "remove-raw-database-secrets"
            reasons.append("Raw database secrets are prohibited")
        elif policy.require_migration_and_rollback and not migration_safe:
            state, action = SqlOutboxRuntimeState.migration_required, "apply-and-verify-outbox-migration"
            reasons.append("Migration and rollback evidence is incomplete")
        elif (policy.require_all_tables and not tables_safe) or (policy.require_integrity_indexes and not indexes_safe):
            state, action = SqlOutboxRuntimeState.schema_rejected, "repair-outbox-schema-contract"
            reasons.append("Required tables or integrity indexes are missing")
        elif policy.require_workspace_partitioning and not schema.workspace_partition_key:
            state, action = SqlOutboxRuntimeState.schema_rejected, "enforce-workspace-partitioning"
            reasons.append("Workspace partitioning is not verified")
        elif not dependency_ready or not factory_ready or not relay_ready:
            state, action = SqlOutboxRuntimeState.relay_unavailable, "verify-sql-relay-runtime"
            reasons.append("Database dependency, factory or relay readiness is incomplete")
        elif not concurrency_safe or (policy.require_lease_and_heartbeat and not recovery_safe):
            state, action = SqlOutboxRuntimeState.worker_degraded, "repair-worker-concurrency-and-leases"
            reasons.append("Worker concurrency, lease or heartbeat safety is incomplete")
        elif policy.require_broker_publish_and_checkpoint and not publication_safe:
            state, action = SqlOutboxRuntimeState.worker_degraded, "verify-publish-checkpoint-boundary"
            reasons.append("Broker publish and checkpoint commit are not both verified")
        elif policy.require_graceful_shutdown and not lifecycle_safe:
            state, action = SqlOutboxRuntimeState.worker_degraded, "verify-worker-lifecycle"
            reasons.append("Worker shutdown or health probe is incomplete")
        elif not backlog_safe:
            state, action = SqlOutboxRuntimeState.worker_degraded, "drain-outbox-backlog"
            reasons.append("Backlog, record age, latency or failure budget exceeds policy")
        elif not schema_safe:
            state, action = SqlOutboxRuntimeState.schema_rejected, "repair-sql-outbox-schema"
            reasons.append("SQL outbox schema integrity is incomplete")
        else:
            state, action = SqlOutboxRuntimeState.runtime_ready, "accept-sql-outbox-runtime"
            reasons.append("SQL schema, relay and publisher worker passed all gates")

        dispatchable = state == SqlOutboxRuntimeState.runtime_ready
        if dispatchable:
            state = SqlOutboxRuntimeState.dispatched
            action = "dispatch-sql-runtime-to-v18-65"
            reasons.append("SQL outbox runtime is ready for transactional outbox execution")

        schema_score = 100 if schema_safe else 0
        migration_score = 100 if migration_safe else 0
        relay_score = 100 if dependency_ready and factory_ready and relay_ready else 0
        worker_score = 100 if concurrency_safe and recovery_safe and publication_safe and lifecycle_safe else 0
        backlog_score = 100 if backlog_safe else 0
        confidence = round((schema_score + migration_score + relay_score + worker_score + backlog_score) / 5)
        record = SqlOutboxRuntimeAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            runtime_id=payload.runtime_id,
            database_type=payload.database_type,
            schema_version=payload.schema_version,
            relay_mode=payload.relay_mode,
            state=state,
            dispatchable=dispatchable,
            target_module="executive-transactional-outbox" if dispatchable else None,
            recommended_action=action,
            scores=SqlOutboxRuntimeScores(
                schema_integrity=schema_score,
                migration_safety=migration_score,
                relay_readiness=relay_score,
                worker_resilience=worker_score,
                backlog_health=backlog_score,
                runtime_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._runtime_versions.add(runtime_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, actor_id=payload.actor_id, action=action))
        return record

    def list_assessments(self, workspace_id: str) -> list[SqlOutboxRuntimeAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> SqlOutboxRuntimeAssessment | None:
        record = self._records.get(assessment_id)
        return record if record and record.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> SqlOutboxRuntimeStatusResponse:
        records = self.list_assessments(workspace_id)
        return SqlOutboxRuntimeStatusResponse(
            workspace_id=workspace_id,
            assessments=len(records),
            ready_runtimes=sum(record.state == SqlOutboxRuntimeState.dispatched for record in records),
            degraded_runtimes=sum(record.state in {SqlOutboxRuntimeState.worker_degraded, SqlOutboxRuntimeState.relay_unavailable} for record in records),
            latest_state=records[-1].state if records else None,
        )


executive_sql_outbox_runtime_service = ExecutiveSqlOutboxRuntimeService()
