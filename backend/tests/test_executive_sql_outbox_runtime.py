from app.modules.executive_sql_outbox_runtime.models import (
    DatabaseType,
    RelayMode,
    RelayWorkerObservation,
    SqlOutboxRuntimeAssessmentCreate,
    SqlOutboxRuntimeState,
    SqlSchemaObservation,
)
from app.modules.executive_sql_outbox_runtime.service import ExecutiveSqlOutboxRuntimeService


def valid_payload(workspace_id: str = "ws-1") -> SqlOutboxRuntimeAssessmentCreate:
    return SqlOutboxRuntimeAssessmentCreate(
        workspace_id=workspace_id,
        source_key="sql-runtime-1",
        actor_id="tester",
        transactional_outbox_assessment_id="outbox-1",
        transactional_outbox_state="dispatched",
        runtime_id="publisher-runtime",
        database_type=DatabaseType.postgresql,
        schema_version="001",
        relay_mode=RelayMode.polling,
        schema_observation=SqlSchemaObservation(
            migration_present=True,
            migration_applied=True,
            rollback_verified=True,
            outbox_table_exists=True,
            inbox_table_exists=True,
            checkpoint_table_exists=True,
            primary_keys_verified=True,
            unique_event_id_index=True,
            unique_idempotency_index=True,
            unpublished_scan_index=True,
            lease_expiry_index=True,
            workspace_partition_key=True,
            payload_json_validated=True,
        ),
        worker_observation=RelayWorkerObservation(
            database_connection_verified=True,
            polling_query_verified=True,
            skip_locked_verified=True,
            lease_claim_verified=True,
            heartbeat_verified=True,
            broker_publish_verified=True,
            checkpoint_commit_verified=True,
            graceful_shutdown_verified=True,
            health_probe_verified=True,
        ),
    )


def test_dispatches_verified_runtime() -> None:
    result = ExecutiveSqlOutboxRuntimeService().create(valid_payload())
    assert result.state == SqlOutboxRuntimeState.dispatched
    assert result.dispatchable is True


def test_requires_migration() -> None:
    payload = valid_payload()
    payload.schema_observation.migration_applied = False
    assert ExecutiveSqlOutboxRuntimeService().create(payload).state == SqlOutboxRuntimeState.migration_required


def test_rejects_raw_secrets() -> None:
    payload = valid_payload()
    payload.schema_observation.raw_secrets_present = True
    assert ExecutiveSqlOutboxRuntimeService().create(payload).state == SqlOutboxRuntimeState.blocked


def test_requires_skip_locked_for_multiple_workers() -> None:
    payload = valid_payload()
    payload.worker_observation.worker_count = 2
    payload.worker_observation.skip_locked_verified = False
    assert ExecutiveSqlOutboxRuntimeService().create(payload).state == SqlOutboxRuntimeState.worker_degraded


def test_detects_backlog_degradation() -> None:
    payload = valid_payload()
    payload.worker_observation.backlog_records = 100_001
    assert ExecutiveSqlOutboxRuntimeService().create(payload).state == SqlOutboxRuntimeState.worker_degraded


def test_risk_brain_blocks() -> None:
    payload = valid_payload()
    payload.risk_brain_clear = False
    assert ExecutiveSqlOutboxRuntimeService().create(payload).state == SqlOutboxRuntimeState.blocked


def test_duplicate_runtime_rejected() -> None:
    service = ExecutiveSqlOutboxRuntimeService()
    service.create(valid_payload())
    payload = valid_payload()
    payload.source_key = "sql-runtime-2"
    try:
        service.create(payload)
    except ValueError as exc:
        assert "Duplicate SQL outbox runtime schema version" in str(exc)
    else:
        raise AssertionError("duplicate runtime was accepted")


def test_workspace_isolation() -> None:
    service = ExecutiveSqlOutboxRuntimeService()
    record = service.create(valid_payload())
    assert service.get(record.id, "other") is None
