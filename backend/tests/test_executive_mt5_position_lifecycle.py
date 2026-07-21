from uuid import uuid4

import pytest

from app.executive_mt5_position_lifecycle.models import (
    MT5PositionLifecycleCreate,
    MT5PositionLifecycleState,
    PositionActionRequest,
    PositionLifecycleObservation,
)
from app.executive_mt5_position_lifecycle.service import executive_mt5_position_lifecycle_service


def build_payload(**overrides):
    values = {
        "execution_state": "execution-complete",
        "position_exists": True,
        "position_ticket": 123456,
        "symbol": "XAUUSD",
        "current_volume": 0.10,
        "action": "modify",
        "requested_volume": 0.0,
        "requested_stop_loss": 2300.0,
        "requested_take_profit": 2400.0,
        "price_precision_valid": True,
        "volume_step_valid": True,
        "stop_level_valid": True,
        "freeze_level_clear": True,
        "risk_policy_clear": True,
        "prop_rule_clear": True,
        "human_approval_verified": True,
        "command_dispatched": True,
        "broker_acknowledged": True,
        "broker_retcode_success": True,
        "deal_event_ingested": True,
        "closed_volume": 0.0,
        "remaining_volume": 0.10,
        "resulting_stop_loss_verified": True,
        "resulting_take_profit_verified": True,
        "position_reconciled": True,
        "account_snapshot_reconciled": True,
        "terminal_error": False,
    }
    values.update(overrides)
    return MT5PositionLifecycleCreate(
        workspace_id="ws-a",
        source_key=str(uuid4()),
        actor_id="operator",
        observation=PositionLifecycleObservation(**values),
    )


def setup_function():
    executive_mt5_position_lifecycle_service.reset()


def test_modify_lifecycle_complete():
    record = executive_mt5_position_lifecycle_service.assess(build_payload())
    assert record.state == MT5PositionLifecycleState.lifecycle_complete


def test_execution_dependency():
    record = executive_mt5_position_lifecycle_service.assess(build_payload(execution_state="deal-ingestion-pending"))
    assert record.state == MT5PositionLifecycleState.execution_required


def test_missing_position():
    record = executive_mt5_position_lifecycle_service.assess(build_payload(position_exists=False))
    assert record.state == MT5PositionLifecycleState.position_missing


def test_invalid_action():
    record = executive_mt5_position_lifecycle_service.assess(build_payload(action="delete"))
    assert record.state == MT5PositionLifecycleState.request_invalid


def test_partial_close_volume_validation():
    record = executive_mt5_position_lifecycle_service.assess(build_payload(action="partial-close", requested_volume=0.10))
    assert record.state == MT5PositionLifecycleState.request_invalid


def test_protection_validation():
    record = executive_mt5_position_lifecycle_service.assess(build_payload(stop_level_valid=False))
    assert record.state == MT5PositionLifecycleState.protection_invalid


def test_risk_brain_block():
    payload = build_payload()
    payload.risk_brain_clear = False
    record = executive_mt5_position_lifecycle_service.assess(payload)
    assert record.state == MT5PositionLifecycleState.blocked


def test_human_approval_required():
    record = executive_mt5_position_lifecycle_service.assess(build_payload(human_approval_verified=False))
    assert record.state == MT5PositionLifecycleState.approval_required


def test_broker_ack_pending():
    record = executive_mt5_position_lifecycle_service.assess(build_payload(broker_acknowledged=False))
    assert record.state == MT5PositionLifecycleState.broker_ack_pending


def test_close_deal_event_pending():
    record = executive_mt5_position_lifecycle_service.assess(build_payload(action="full-close", requested_volume=0.10, deal_event_ingested=False))
    assert record.state == MT5PositionLifecycleState.deal_event_pending


def test_terminal_error():
    record = executive_mt5_position_lifecycle_service.assess(build_payload(terminal_error=True))
    assert record.state == MT5PositionLifecycleState.lifecycle_failed


def test_duplicate_source_key():
    payload = build_payload()
    executive_mt5_position_lifecycle_service.assess(payload)
    with pytest.raises(ValueError):
        executive_mt5_position_lifecycle_service.assess(payload.model_copy(update={"lifecycle_id": uuid4()}))


def test_workspace_isolation():
    record = executive_mt5_position_lifecycle_service.assess(build_payload())
    assert executive_mt5_position_lifecycle_service.get(record.id, "ws-b") is None
    assert executive_mt5_position_lifecycle_service.list_records("ws-b") == []


def test_execute_completes_pending_record():
    record = executive_mt5_position_lifecycle_service.assess(build_payload(command_dispatched=False))
    result = executive_mt5_position_lifecycle_service.execute(
        PositionActionRequest(
            workspace_id="ws-a",
            lifecycle_id=record.lifecycle_id,
            actor_id="operator",
            human_approval_verified=True,
            command_dispatched=True,
            broker_acknowledged=True,
            broker_retcode_success=True,
            deal_event_ingested=True,
            closed_volume=0.0,
            remaining_volume=0.10,
            resulting_stop_loss_verified=True,
            resulting_take_profit_verified=True,
            position_reconciled=True,
            account_snapshot_reconciled=True,
        )
    )
    assert result.state == MT5PositionLifecycleState.lifecycle_complete
