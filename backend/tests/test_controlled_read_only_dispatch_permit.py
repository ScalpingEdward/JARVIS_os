import pytest

from app.schemas.controlled_read_only_dispatch_permit import (
    DispatchPermitAction,
    DispatchPermitConsume,
    DispatchPermitCreate,
)
from app.services.controlled_read_only_dispatch_permit import ControlledReadOnlyDispatchPermitService


def payload(**overrides):
    data = {
        "workspace_id": "ws-a",
        "source_key": "permit-source-001",
        "requested_by": "orchestrator",
        "authorization_chain_record_id": "chain-001",
        "authorization_chain_digest": "sha256:chain-digest",
        "authorization_chain_state": "eligible",
        "operation": "read-repository",
        "target": "https://api.github.com/repos/ScalpingEdward/JARVIS_os",
        "method": "GET",
        "adapter_id": "github-readonly-adapter",
        "worker_id": "worker-a",
        "gateway_record_id": "gateway-001",
        "dispatch_token_digest": "sha256:dispatch-token",
        "ttl_seconds": 120,
        "max_uses": 1,
        "criticality": 0.6,
    }
    data.update(overrides)
    return DispatchPermitCreate(**data)


def action(name, op):
    return DispatchPermitAction(workspace_id="ws-a", action=name, actor="owner", operation_id=op)


def consume_for(record, op="op-3"):
    return DispatchPermitConsume(
        workspace_id="ws-a",
        actor="worker-a",
        operation_id=op,
        permit_token_digest=record.permit_token_digest,
        authorization_chain_digest=record.authorization_chain_digest,
        dispatch_token_digest=record.dispatch_token_digest,
        adapter_id=record.adapter_id,
        worker_id=record.worker_id,
    )


def test_status_exposes_single_use_read_only_boundary():
    status = ControlledReadOnlyDispatchPermitService().status()
    assert status["version"] == "21.129"
    assert status["permit_max_uses"] == 1
    assert status["external_dispatch_executed_by_module"] is False
    assert status["trading_execution_enabled"] is False


def test_safe_permit_lifecycle_is_single_use():
    service = ControlledReadOnlyDispatchPermitService()
    record = service.create(payload())
    assert record.state.value == "review-required"
    record = service.act(record.permit_id, action("approve", "op-1"))
    record = service.act(record.permit_id, action("issue", "op-2"))
    assert record.state.value == "issued"
    assert record.permit_token_digest
    assert record.expires_at
    record = service.consume(record.permit_id, consume_for(record))
    assert record.state.value == "consumed"
    with pytest.raises(ValueError, match="issued permit required"):
        service.consume(record.permit_id, consume_for(record, "op-4"))


def test_binding_mismatch_blocks_consumption():
    service = ControlledReadOnlyDispatchPermitService()
    record = service.create(payload())
    record = service.act(record.permit_id, action("approve", "op-1"))
    record = service.act(record.permit_id, action("issue", "op-2"))
    bad = consume_for(record)
    bad.adapter_id = "wrong-adapter"
    with pytest.raises(ValueError, match="binding mismatch"):
        service.consume(record.permit_id, bad)


def test_protected_operation_is_risk_brain_blocked():
    service = ControlledReadOnlyDispatchPermitService()
    record = service.create(payload(operation="trade-execute"))
    assert record.state.value == "blocked"
    assert "risk-brain-hard-block" in record.risk_flags


def test_upstream_hard_block_propagates():
    service = ControlledReadOnlyDispatchPermitService()
    record = service.create(payload(risk_brain_hard_blocked=True))
    assert record.state.value == "blocked"
    assert "upstream-risk-brain-hard-block" in record.risk_flags


def test_replay_and_workspace_isolation():
    service = ControlledReadOnlyDispatchPermitService()
    record = service.create(payload())
    service.act(record.permit_id, action("approve", "same-op"))
    with pytest.raises(ValueError, match="replay"):
        service.act(record.permit_id, action("issue", "same-op"))
    with pytest.raises(KeyError):
        service.get("ws-b", record.permit_id)


def test_duplicate_source_key_rejected():
    service = ControlledReadOnlyDispatchPermitService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
