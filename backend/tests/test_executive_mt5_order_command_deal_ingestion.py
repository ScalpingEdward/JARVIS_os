from uuid import uuid4

import pytest

from app.executive_mt5_order_command_deal_ingestion.models import DispatchRequest, MT5ExecutionCreate, MT5ExecutionState, MT5OrderObservation
from app.executive_mt5_order_command_deal_ingestion.service import executive_mt5_order_command_deal_ingestion_service as service


def payload(**overrides):
    values = {
        "bridge_state": "bridge-ready",
        "command_schema_valid": True,
        "symbol_mapping_verified": True,
        "side_valid": True,
        "requested_volume": 0.1,
        "normalized_volume": 0.1,
        "stop_loss_valid": True,
        "take_profit_valid": True,
        "price_deviation_within_budget": True,
        "account_risk_clear": True,
        "prop_rules_clear": True,
        "idempotency_key_verified": True,
        "command_dispatched": True,
        "broker_acknowledged": True,
        "broker_order_id": "1001",
        "broker_retcode_success": True,
        "deal_events_received": 1,
        "requested_fill_volume": 0.1,
        "actual_fill_volume": 0.1,
        "average_fill_price_verified": True,
        "position_ticket_verified": True,
        "account_snapshot_reconciled": True,
        "position_reconciled": True,
        "pending_orders_reconciled": True,
    }
    values.update(overrides)
    return MT5ExecutionCreate(workspace_id="ws", source_key=str(uuid4()), actor_id="human", bridge_id=uuid4(), account_reference="demo", symbol="XAUUSD", side="buy", observation=MT5OrderObservation(**values))


def setup_function():
    service.reset()


def test_execution_complete():
    assert service.assess(payload()).state == MT5ExecutionState.execution_complete

@pytest.mark.parametrize(("overrides", "state"), [
    ({"bridge_state": "approval-required"}, MT5ExecutionState.bridge_required),
    ({"command_schema_valid": False}, MT5ExecutionState.command_invalid),
    ({"account_risk_clear": False}, MT5ExecutionState.risk_rejected),
    ({"command_dispatched": False}, MT5ExecutionState.dispatch_required),
    ({"broker_acknowledged": False}, MT5ExecutionState.broker_ack_pending),
    ({"deal_events_received": 0}, MT5ExecutionState.deal_ingestion_pending),
    ({"actual_fill_volume": 0.05}, MT5ExecutionState.partial_fill),
    ({"position_reconciled": False}, MT5ExecutionState.reconciliation_required),
    ({"terminal_error_present": True}, MT5ExecutionState.execution_failed),
])
def test_gates(overrides, state):
    assert service.assess(payload(**overrides)).state == state


def test_risk_brain_block():
    item = payload()
    item.risk_brain_clear = False
    assert service.assess(item).state == MT5ExecutionState.blocked


def test_dispatch_progresses_to_complete():
    created = service.assess(payload(command_dispatched=False))
    request = DispatchRequest(workspace_id="ws", execution_id=created.execution_id, actor_id="human", command_dispatched=True, broker_acknowledged=True, broker_order_id="1002", broker_retcode_success=True, deal_events_received=1, requested_fill_volume=0.1, actual_fill_volume=0.1, average_fill_price_verified=True, position_ticket_verified=True, account_snapshot_reconciled=True, position_reconciled=True, pending_orders_reconciled=True)
    assert service.dispatch(request).state == MT5ExecutionState.execution_complete


def test_duplicate_and_workspace_isolation():
    item = payload()
    service.assess(item)
    with pytest.raises(ValueError):
        service.assess(item)
    assert service.list_records("other") == []
