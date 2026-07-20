from __future__ import annotations

from uuid import UUID

from .models import AuditRecord, RelayMode, SqlOutboxRuntimeAssessment, SqlOutboxRuntimeAssessmentCreate, SqlOutboxRuntimeScores, SqlOutboxRuntimeState, SqlOutboxRuntimeStatusResponse


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
        schema, worker, policy = payload.schema_observation, payload.worker_observation, payload.policy
        reasons: list[str] = []
        migration_safe = schema.migration_present and schema.migration_applied and schema.rollback_verified
        tables_safe = schema.outbox_table_exists and schema.inbox_table_exists and schema.checkpoint_table_exists
        indexes_safe = schema.primary_keys_verified and schema.unique_event_id_index and schema.unique_idempotency_index and schema.unpublished_scan_index and schema.lease_expiry_index
        schema_safe = migration_safe and tables_safe and indexes_safe and schema.workspace_partition_key and schema.payload_json_validated and not schema.raw_secrets_present
        dependency_ready = worker.dependency_installed and worker.import_verified
        factory_ready = worker.repository_factory_verified and worker.relay_factory_verified and worker.worker_factory_verified
        relay_ready = worker.database_connection_verified and (worker.cdc_slot_or_binlog_verified if payload.relay_mode == RelayMode.cdc else worker.polling_query_verified)
        concurrency_safe = not (payload.relay_mode == RelayMode.polling and worker.worker_count > 1 and policy.require_skip_locked_for_multi_worker_polling and not worker.skip_locked_verified)
        recovery_safe = worker.lease_claim_verified and worker.heartbeat_verified
        publication_safe = worker.broker_publish_verified and worker.checkpoint_commit_verified
        lifecycle_safe = worker.graceful_shutdown_verified and worker.health_probe_verified
        backlog_safe = worker.backlog_records <= policy.maximum_backlog_records and worker.oldest_record_age_seconds <= policy.maximum_oldest_record_age_seconds and worker.publish_latency_ms <= policy.maximum_publish_latency_ms and worker.consecutive_failures <= policy.maximum_consecutive_failures

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
        elif (policy.require_all_tables and not tables_safe) or (policy.require_integrity_indexes and not indexes_safe) or (policy.require_workspace_partitioning and not schema.workspace_partition_key):
            state, action = SqlOutboxRuntimeState.schema_rejected, "repair-outbox-schema-contract"
            reasons.append("Required tables, indexes or workspace partitioning are missing")
        elif not dependency_ready or not factory_ready or not relay_ready:
            state, action = SqlOutboxRuntimeState.relay_unavailable, "verify-sql-relay-runtime"
            reasons.append("Database dependency, factory or relay readiness is incomplete")
        elif not concurrency_safe or (policy.require_lease_and_heartbeat and not recovery_safe) or (policy.require_broker_publish_and_checkpoint and not publication_safe) or (policy.require_graceful_shutdown and not lifecycle_safe) or not backlog_safe:
            state, action = SqlOutboxRuntimeState.worker_degraded, "repair-publisher-worker-runtime"
            reasons.append("Worker concurrency, recovery, publication, lifecycle or backlog policy failed")
        elif not schema_safe:
            state, action = SqlOutboxRuntimeState.schema_rejected, "repair-sql-outbox-schema"
            reasons.append("SQL outbox schema integrity is incomplete")
        else:
            state, action = SqlOutboxRuntimeState.runtime_ready, "accept-sql-outbox-runtime"
            reasons.append("SQL schema, relay and publisher worker passed all gates")

        dispatchable = state == SqlOutboxRuntimeState.runtime_ready
        if dispatchable:
            state, action = SqlOutboxRuntimeState.dispatched, "dispatch-sql-runtime-to-v18-65"
            reasons.append("SQL outbox runtime is ready for transactional outbox execution")
        scores = [100 if schema_safe else 0, 100 if migration_safe else 0, 100 if dependency_ready and factory_ready and relay_ready else 0, 100 if concurrency_safe and recovery_safe and publication_safe and lifecycle_safe else 0, 100 if backlog_safe else 0]
        record = SqlOutboxRuntimeAssessment(workspace_id=payload.workspace_id, source_key=payload.source_key, actor_id=payload.actor_id, runtime_id=payload.runtime_id, database_type=payload.database_type, schema_version=payload.schema_version, relay_mode=payload.relay_mode, state=state, dispatchable=dispatchable, target_module="executive-transactional-outbox" if dispatchable else None, recommended_action=action, scores=SqlOutboxRuntimeScores(schema_integrity=scores[0], migration_safety=scores[1], relay_readiness=scores[2], worker_resilience=scores[3], backlog_health=scores[4], runtime_confidence=round(sum(scores) / 5)), reasons=reasons)
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._runtime_versions.add(runtime_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, actor_id=payload.actor_id, action=action))
        return record

    def list_assessments(self, workspace_id: str) -> list[SqlOutboxRuntimeAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> SqlOutboxRuntimeAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> SqlOutboxRuntimeStatusResponse:
        items = self.list_assessments(workspace_id)
        return SqlOutboxRuntimeStatusResponse(workspace_id=workspace_id, assessments=len(items), ready_runtimes=sum(item.state == SqlOutboxRuntimeState.dispatched for item in items), degraded_runtimes=sum(item.state in {SqlOutboxRuntimeState.worker_degraded, SqlOutboxRuntimeState.relay_unavailable} for item in items), latest_state=items[-1].state if items else None)


executive_sql_outbox_runtime_service = ExecutiveSqlOutboxRuntimeService()
