from uuid import uuid4

from app.executive_transactional_outbox.models import OutboxObservation, TransactionalOutboxAssessmentCreate, TransactionalOutboxState
from app.executive_transactional_outbox.service import ExecutiveTransactionalOutboxService


def payload(workspace: str = "ws-a", source: str = "src-a") -> TransactionalOutboxAssessmentCreate:
    return TransactionalOutboxAssessmentCreate(
        workspace_id=workspace,
        source_key=source,
        actor_id="tester",
        persistent_store_assessment_id="store-1",
        persistent_store_state="dispatched",
        transaction_id="tx-1",
        aggregate_id="aggregate-1",
        publisher_id="publisher-1",
        consumer_id="consumer-1",
        idempotency_key=str(uuid4()),
        checkpoint_key=str(uuid4()),
        observation=OutboxObservation(
            business_commit_succeeded=True,
            outbox_inserted_same_transaction=True,
            transaction_id_verified=True,
            event_persisted=True,
            publisher_lease_acquired=True,
            lease_owner_verified=True,
            publish_attempted=True,
            broker_acknowledged=True,
            published_marker_persisted=True,
            checkpoint_persisted=True,
            inbox_record_persisted=True,
            consumer_side_effect_committed=True,
            consumer_ack_persisted=True,
            recovery_scan_completed=True,
            publish_attempts=1,
            latency_ms=25,
        ),
    )


def test_successful_transactional_dispatch() -> None:
    service = ExecutiveTransactionalOutboxService()
    result = service.create(payload())
    assert result.state == TransactionalOutboxState.dispatched
    assert result.dispatchable is True


def test_same_transaction_is_required() -> None:
    service = ExecutiveTransactionalOutboxService()
    item = payload()
    item.observation.outbox_inserted_same_transaction = False
    result = service.create(item)
    assert result.state == TransactionalOutboxState.transaction_required


def test_duplicate_inbox_is_discarded() -> None:
    service = ExecutiveTransactionalOutboxService()
    item = payload()
    item.observation.inbox_duplicate_detected = True
    result = service.create(item)
    assert result.state == TransactionalOutboxState.duplicate


def test_expired_lease_requires_recovery() -> None:
    service = ExecutiveTransactionalOutboxService()
    item = payload()
    item.observation.publisher_lease_acquired = False
    item.observation.lease_expired = True
    result = service.create(item)
    assert result.state == TransactionalOutboxState.recovery_required
    assert result.recoverable is True


def test_missing_broker_ack_requires_recovery() -> None:
    service = ExecutiveTransactionalOutboxService()
    item = payload()
    item.observation.broker_acknowledged = False
    result = service.create(item)
    assert result.state == TransactionalOutboxState.recovery_required


def test_risk_brain_blocks_processing() -> None:
    service = ExecutiveTransactionalOutboxService()
    item = payload()
    item.risk_brain_clear = False
    result = service.create(item)
    assert result.state == TransactionalOutboxState.blocked


def test_duplicate_source_key_is_detected() -> None:
    service = ExecutiveTransactionalOutboxService()
    first = payload()
    service.create(first)
    second = payload(source=first.source_key)
    result = service.create(second)
    assert result.state == TransactionalOutboxState.duplicate


def test_workspace_isolation() -> None:
    service = ExecutiveTransactionalOutboxService()
    result = service.create(payload())
    assert service.get(result.id, "ws-b") is None
    assert service.list_assessments("ws-b") == []
