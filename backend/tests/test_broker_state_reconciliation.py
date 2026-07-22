import pytest

from app.modules.broker_state_reconciliation.models import (
    BrokerSnapshot,
    PositionSnapshot,
    ReconciliationAction,
    ReconciliationCreate,
    ReconciliationState,
)
from app.modules.broker_state_reconciliation.service import (
    BrokerStateReconciliationError,
    BrokerStateReconciliationService,
)


def snapshot(snapshot_id="snap-1", balance=10000, equity=10000, volume=0.1, positions=True):
    items = []
    if positions:
        items = [PositionSnapshot(position_id="pos-1", symbol="XAUUSD", side="buy", volume=volume, entry_price=2400)]
    return BrokerSnapshot(snapshot_id=snapshot_id, account_ref="account-ref", balance=balance, equity=equity, margin_used=100, positions=items)


def payload(**overrides):
    values = {
        "workspace_id": "ws-1",
        "source_key": "recon-1",
        "runtime_record_id": "runtime-1",
        "command_record_ids": ["command-1"],
        "expected_snapshot": snapshot("expected"),
        "broker_snapshot": snapshot("actual"),
        "upstream_evidence_verified": True,
    }
    values.update(overrides)
    return ReconciliationCreate(**values)


def test_matching_snapshot_resolves_without_correction():
    service = BrokerStateReconciliationService()
    record = service.create(payload())
    assert record.state == ReconciliationState.MATCHED
    record = service.act(record.record_id, "ws-1", ReconciliationAction(action="resolve", actor_id="system", receipt_id="resolve-1"))
    assert record.state == ReconciliationState.RESOLVED


def test_drift_requires_approval_and_correction_receipts():
    service = BrokerStateReconciliationService()
    record = service.create(payload(broker_snapshot=snapshot("actual", equity=9975, volume=0.2)))
    assert record.state == ReconciliationState.HUMAN_REVIEW_REQUIRED
    assert record.drifts

    record = service.act(record.record_id, "ws-1", ReconciliationAction(action="approve", actor_id="operator", approval_token="approval-1"))
    assert record.state == ReconciliationState.APPROVED
    record = service.act(record.record_id, "ws-1", ReconciliationAction(action="queue-correction", actor_id="operator", receipt_id="queue-1"))
    assert record.state == ReconciliationState.CORRECTION_QUEUED
    record = service.act(record.record_id, "ws-1", ReconciliationAction(action="resolve", actor_id="broker", receipt_id="resolve-1"))
    assert record.state == ReconciliationState.RESOLVED


def test_missing_and_unexpected_positions_are_critical_drift():
    service = BrokerStateReconciliationService()
    record = service.create(payload(broker_snapshot=snapshot("actual", positions=False)))
    assert record.state == ReconciliationState.HUMAN_REVIEW_REQUIRED
    assert any(item.severity.value == "critical" for item in record.drifts)


def test_governance_gates_replay_and_workspace_isolation():
    service = BrokerStateReconciliationService()
    assert service.create(payload(source_key="blocked", risk_brain_blocked=True)).state == ReconciliationState.BLOCKED
    assert service.create(payload(source_key="missing", upstream_evidence_verified=False)).state == ReconciliationState.EVIDENCE_REQUIRED

    record = service.create(payload(source_key="drift", broker_snapshot=snapshot("actual", balance=9990)))
    service.act(record.record_id, "ws-1", ReconciliationAction(action="approve", actor_id="operator", approval_token="token"))
    with pytest.raises(BrokerStateReconciliationError, match="replay"):
        second = service.create(payload(source_key="drift-2", broker_snapshot=snapshot("actual-2", balance=9990)))
        service.act(second.record_id, "ws-1", ReconciliationAction(action="approve", actor_id="operator", approval_token="token"))

    service.act(record.record_id, "ws-1", ReconciliationAction(action="queue-correction", actor_id="operator", receipt_id="receipt"))
    with pytest.raises(BrokerStateReconciliationError, match="replay"):
        service.act(record.record_id, "ws-1", ReconciliationAction(action="resolve", actor_id="operator", receipt_id="receipt"))
    with pytest.raises(BrokerStateReconciliationError, match="not found"):
        service.get(record.record_id, "ws-2")


def test_duplicate_source_and_position_ids_are_rejected():
    service = BrokerStateReconciliationService()
    service.create(payload())
    with pytest.raises(BrokerStateReconciliationError, match="duplicate source"):
        service.create(payload())
    with pytest.raises(ValueError, match="duplicate position"):
        BrokerSnapshot(snapshot_id="bad", account_ref="account-ref", balance=1, equity=1, margin_used=0, positions=[
            PositionSnapshot(position_id="x", symbol="XAUUSD", side="buy", volume=0.1, entry_price=1),
            PositionSnapshot(position_id="x", symbol="XAUUSD", side="buy", volume=0.1, entry_price=1),
        ])
