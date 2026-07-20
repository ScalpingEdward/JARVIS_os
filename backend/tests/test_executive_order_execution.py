from uuid import uuid4

import pytest

from app.executive_order_execution.models import ExecutionAssessmentCreate, ExecutionObservation, ExecutionState, ReconcileRequest
from app.executive_order_execution.service import executive_order_execution_service


@pytest.fixture(autouse=True)
def reset_service() -> None:
    executive_order_execution_service.reset()


def payload(**changes):
    observation = changes.pop("observation", ExecutionObservation(requested_quantity=1, filled_quantity=1, average_fill_price=2000, expected_price=2000))
    data = dict(workspace_id="ws-a", source_key=str(uuid4()), actor_id="operator", order_intent_id=uuid4(), adapter="mt5", account_reference="acct-1", canonical_symbol="XAUUSD", idempotency_key=str(uuid4()), observation=observation)
    data.update(changes)
    return ExecutionAssessmentCreate(**data)


def test_completed_execution() -> None:
    record = executive_order_execution_service.assess(payload())
    assert record.state == ExecutionState.execution_completed
    assert record.reconciliation_complete is True


def test_requires_human_approval() -> None:
    o = ExecutionObservation(requested_quantity=1, filled_quantity=0, human_approval_verified=False)
    assert executive_order_execution_service.assess(payload(observation=o)).state == ExecutionState.approval_required


def test_risk_brain_blocks() -> None:
    assert executive_order_execution_service.assess(payload(risk_brain_clear=False)).state == ExecutionState.blocked


def test_adapter_unavailable() -> None:
    o = ExecutionObservation(requested_quantity=1, filled_quantity=0, adapter_healthy=False)
    assert executive_order_execution_service.assess(payload(observation=o)).state == ExecutionState.adapter_unavailable


def test_partial_fill() -> None:
    o = ExecutionObservation(requested_quantity=2, filled_quantity=1, average_fill_price=2000, expected_price=2000)
    assert executive_order_execution_service.assess(payload(observation=o)).state == ExecutionState.partial_fill


def test_duplicate_fill_requires_reconciliation() -> None:
    o = ExecutionObservation(requested_quantity=1, filled_quantity=1, duplicate_fill_detected=True)
    assert executive_order_execution_service.assess(payload(observation=o)).state == ExecutionState.reconciliation_required


def test_slippage_requires_reconciliation() -> None:
    o = ExecutionObservation(requested_quantity=1, filled_quantity=1, average_fill_price=2010, expected_price=2000, maximum_slippage_bps=10)
    assert executive_order_execution_service.assess(payload(observation=o)).state == ExecutionState.reconciliation_required


def test_duplicate_idempotency_rejected() -> None:
    key = "same-key"
    executive_order_execution_service.assess(payload(idempotency_key=key))
    with pytest.raises(ValueError):
        executive_order_execution_service.assess(payload(idempotency_key=key))


def test_workspace_isolation_and_reconcile() -> None:
    o = ExecutionObservation(requested_quantity=1, filled_quantity=1, broker_position_reconciled=False)
    record = executive_order_execution_service.assess(payload(observation=o))
    assert executive_order_execution_service.get(record.id, "ws-b") is None
    reconciled = executive_order_execution_service.reconcile(ReconcileRequest(workspace_id="ws-a", execution_id=record.execution_id, actor_id="operator"))
    assert reconciled.state == ExecutionState.execution_completed
