from uuid import uuid4

import pytest

from app.executive_mt5_runtime_bridge.models import BridgeStartRequest, MT5RuntimeBridgeCreate, MT5RuntimeBridgeState, MT5RuntimeObservation
from app.executive_mt5_runtime_bridge.service import executive_mt5_runtime_bridge_service


def make_payload(**overrides):
    observation_values = {
        "live_adapter_state": "production-ready",
        "terminal_process_running": True,
        "terminal_version_verified": True,
        "terminal_path_verified": True,
        "account_login_verified": True,
        "expected_account_login": 123456,
        "observed_account_login": 123456,
        "broker_server_verified": True,
        "trade_mode_enabled": True,
        "algo_trading_enabled": True,
        "market_connected": True,
        "symbol_mapping_verified": True,
        "volume_step_verified": True,
        "filling_mode_verified": True,
        "stop_level_verified": True,
        "execution_probe_completed": True,
        "execution_probe_errors": 0,
        "execution_probe_reconciled": True,
        "human_approval_verified": True,
        "bridge_started": True,
        "bridge_acknowledged": True,
        "positions_reconciled": True,
        "pending_orders_reconciled": True,
        "account_snapshot_reconciled": True,
    }
    observation_values.update(overrides.pop("observation_overrides", {}))
    values = {
        "workspace_id": "workspace-a",
        "source_key": str(uuid4()),
        "actor_id": "operator",
        "terminal_reference": "mt5-primary",
        "account_reference": "prop-account-1",
        "risk_brain_clear": True,
        "observation": MT5RuntimeObservation(**observation_values),
    }
    values.update(overrides)
    return MT5RuntimeBridgeCreate(**values)


def setup_function():
    executive_mt5_runtime_bridge_service.reset()


def test_bridge_ready():
    record = executive_mt5_runtime_bridge_service.assess(make_payload())
    assert record.state == MT5RuntimeBridgeState.bridge_ready
    assert record.order_submission_enabled is True


def test_risk_brain_blocks():
    record = executive_mt5_runtime_bridge_service.assess(make_payload(risk_brain_clear=False))
    assert record.state == MT5RuntimeBridgeState.blocked


def test_live_activation_required():
    record = executive_mt5_runtime_bridge_service.assess(make_payload(observation_overrides={"live_adapter_state": "approval-required"}))
    assert record.state == MT5RuntimeBridgeState.activation_required


def test_terminal_unavailable():
    record = executive_mt5_runtime_bridge_service.assess(make_payload(observation_overrides={"terminal_process_running": False}))
    assert record.state == MT5RuntimeBridgeState.terminal_unavailable


def test_account_mismatch():
    record = executive_mt5_runtime_bridge_service.assess(make_payload(observation_overrides={"observed_account_login": 999999}))
    assert record.state == MT5RuntimeBridgeState.account_mismatch


def test_symbol_mapping_required():
    record = executive_mt5_runtime_bridge_service.assess(make_payload(observation_overrides={"symbol_mapping_verified": False}))
    assert record.state == MT5RuntimeBridgeState.symbol_mapping_required


def test_trading_permission_required():
    record = executive_mt5_runtime_bridge_service.assess(make_payload(observation_overrides={"algo_trading_enabled": False}))
    assert record.state == MT5RuntimeBridgeState.trading_permission_required


def test_execution_probe_required():
    record = executive_mt5_runtime_bridge_service.assess(make_payload(observation_overrides={"execution_probe_errors": 1}))
    assert record.state == MT5RuntimeBridgeState.execution_probe_required


def test_approval_required():
    record = executive_mt5_runtime_bridge_service.assess(make_payload(observation_overrides={"human_approval_verified": False}))
    assert record.state == MT5RuntimeBridgeState.approval_required


def test_start_bridge_requires_reconciliation():
    record = executive_mt5_runtime_bridge_service.assess(make_payload(observation_overrides={"bridge_started": False, "bridge_acknowledged": False}))
    result = executive_mt5_runtime_bridge_service.start_bridge(BridgeStartRequest(
        workspace_id=record.workspace_id,
        bridge_id=record.bridge_id,
        actor_id="operator",
        human_approval_verified=True,
        bridge_started=True,
        bridge_acknowledged=True,
        positions_reconciled=False,
        pending_orders_reconciled=True,
        account_snapshot_reconciled=True,
    ))
    assert result.state == MT5RuntimeBridgeState.reconciliation_required


def test_duplicate_source_key_rejected():
    payload = make_payload(source_key="same-key")
    executive_mt5_runtime_bridge_service.assess(payload)
    with pytest.raises(ValueError):
        executive_mt5_runtime_bridge_service.assess(make_payload(source_key="same-key"))


def test_workspace_isolation():
    record = executive_mt5_runtime_bridge_service.assess(make_payload())
    assert executive_mt5_runtime_bridge_service.get(record.id, "workspace-b") is None
    assert executive_mt5_runtime_bridge_service.list_records("workspace-b") == []
