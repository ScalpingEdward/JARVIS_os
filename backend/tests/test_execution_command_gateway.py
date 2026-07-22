import pytest

from app.modules.execution_command_gateway.models import (
    BrokerKind,
    CommandAction,
    CommandState,
    CommandType,
    ExecutionCommandCreate,
    GatewayCommand,
)
from app.modules.execution_command_gateway.service import ExecutionCommandGatewayService, GatewayError


def payload(**overrides):
    data = {
        "workspace_id": "ws-1",
        "source_key": "source-1",
        "workflow_record_id": "workflow-1",
        "policy_record_id": "policy-1",
        "broker": BrokerKind.MT5,
        "account_id": "account-1",
        "command_type": CommandType.PLACE_ORDER,
        "symbol": "xauusd",
        "side": "buy",
        "volume": 0.1,
        "order_type": "market",
        "stop_loss": 2300.0,
        "take_profit": 2400.0,
        "idempotency_key": "idem-key-0001",
        "upstream_evidence_verified": True,
        "active_policy_verified": True,
        "workflow_dispatch_verified": True,
    }
    data.update(overrides)
    return ExecutionCommandCreate(**data)


def test_governed_command_lifecycle():
    service = ExecutionCommandGatewayService()
    record = service.create(payload())
    assert record.state == CommandState.HUMAN_REVIEW_REQUIRED
    assert record.symbol == "XAUUSD"
    assert record.validation and record.validation.valid

    record = service.act("ws-1", record.id, CommandAction(
        command=GatewayCommand.APPROVE,
        actor="operator",
        approval_token="approval-1",
    ))
    assert record.state == CommandState.APPROVED

    record = service.act("ws-1", record.id, CommandAction(
        command=GatewayCommand.QUEUE,
        actor="gateway",
        queue_receipt="queue-1",
    ))
    assert record.state == CommandState.QUEUED

    record = service.act("ws-1", record.id, CommandAction(
        command=GatewayCommand.DISPATCH,
        actor="gateway",
        dispatch_receipt="dispatch-1",
    ))
    assert record.state == CommandState.DISPATCHED

    record = service.act("ws-1", record.id, CommandAction(
        command=GatewayCommand.ACKNOWLEDGE,
        actor="adapter",
        broker_receipt="broker-1",
    ))
    assert record.state == CommandState.ACKNOWLEDGED


def test_risk_brain_and_evidence_fail_closed():
    service = ExecutionCommandGatewayService()
    blocked = service.create(payload(source_key="blocked", idempotency_key="idem-blocked", risk_brain_blocked=True))
    assert blocked.state == CommandState.BLOCKED

    missing = service.create(payload(
        source_key="missing",
        idempotency_key="idem-missing",
        upstream_evidence_verified=False,
    ))
    assert missing.state == CommandState.EVIDENCE_REQUIRED


def test_adapter_validation_blocks_invalid_pending_order():
    service = ExecutionCommandGatewayService()
    record = service.create(payload(
        source_key="invalid",
        idempotency_key="idem-invalid",
        order_type="limit",
        price=None,
    ))
    assert record.state == CommandState.VALIDATION_FAILED
    assert "pending-order-price-required" in record.validation.violations


def test_idempotency_and_receipt_replay_protection():
    service = ExecutionCommandGatewayService()
    record = service.create(payload())
    with pytest.raises(GatewayError):
        service.create(payload(source_key="source-2"))

    service.act("ws-1", record.id, CommandAction(
        command=GatewayCommand.APPROVE,
        actor="operator",
        approval_token="approval-1",
    ))
    second = service.create(payload(source_key="source-3", idempotency_key="idem-key-0003"))
    with pytest.raises(GatewayError):
        service.act("ws-1", second.id, CommandAction(
            command=GatewayCommand.APPROVE,
            actor="operator",
            approval_token="approval-1",
        ))


def test_workspace_isolation():
    service = ExecutionCommandGatewayService()
    record = service.create(payload())
    with pytest.raises(GatewayError):
        service.get("ws-2", record.id)
    assert service.list("ws-2") == []
