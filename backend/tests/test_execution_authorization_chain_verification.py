import pytest

from app.schemas.execution_authorization_chain_verification import (
    AuthorizationChainAction,
    AuthorizationChainCreate,
)
from app.services.execution_authorization_chain_verification import (
    ExecutionAuthorizationChainVerificationService,
)


def payload(**overrides):
    workspace = overrides.pop("workspace_id", "ws-a")
    operation = overrides.pop("expected_operation", "read-repository")
    target = overrides.pop("expected_target", "api.github.com/repos/ScalpingEdward/JARVIS_os")
    links = [
        {"stage": "decision", "record_id": "d-1", "digest": "sha256:decision", "state": "ready", "workspace_id": workspace, "human_approved": True},
        {"stage": "proposal", "record_id": "p-1", "digest": "sha256:proposal", "state": "authorized", "workspace_id": workspace, "operation": operation, "target": target, "human_approved": True},
        {"stage": "binding", "record_id": "b-1", "digest": "sha256:binding", "state": "ready", "workspace_id": workspace, "operation": operation, "target": target, "human_approved": True},
        {"stage": "sandbox", "record_id": "s-1", "digest": "sha256:sandbox", "state": "authorized", "workspace_id": workspace, "operation": operation, "human_approved": True},
        {"stage": "adapter", "record_id": "a-1", "digest": "sha256:adapter", "state": "active", "workspace_id": workspace, "operation": operation, "target": target, "human_approved": True},
        {"stage": "gateway", "record_id": "g-1", "digest": "sha256:gateway", "state": "dispatch-ready", "workspace_id": workspace, "operation": operation, "target": target, "human_approved": True},
        {"stage": "worker", "record_id": "w-1", "digest": "sha256:worker", "state": "leased", "workspace_id": workspace, "operation": operation, "target": target, "human_approved": True},
    ]
    data = {
        "workspace_id": workspace,
        "source_key": "chain-001",
        "requested_by": "orchestrator",
        "links": links,
        "expected_operation": operation,
        "expected_target": target,
        "criticality": 0.7,
    }
    data.update(overrides)
    return AuthorizationChainCreate(**data)


def action(name, op):
    return AuthorizationChainAction(workspace_id="ws-a", action=name, actor="owner", operation_id=op)


def test_status_keeps_execution_disabled():
    status = ExecutionAuthorizationChainVerificationService().status()
    assert status["version"] == "21.128"
    assert status["controlled_read_only_dispatch_eligibility_enabled"] is True
    assert status["dispatch_execution_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_complete_chain_can_be_verified_approved_and_marked_eligible():
    service = ExecutionAuthorizationChainVerificationService()
    record = service.create(payload())
    assert record.state.value == "review-required"
    assert not record.risk_flags
    record = service.act(record.record_id, action("verify", "op-1"))
    record = service.act(record.record_id, action("approve", "op-2"))
    record = service.act(record.record_id, action("mark-eligible", "op-3"))
    assert record.state.value == "eligible"
    assert record.approved_by == "owner"


def test_operation_binding_mismatch_blocks_verification():
    p = payload()
    p.links[5].operation = "read-file"
    service = ExecutionAuthorizationChainVerificationService()
    record = service.create(p)
    assert any(flag.startswith("operation-binding-mismatch") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block verification"):
        service.act(record.record_id, action("verify", "op-a"))


def test_upstream_risk_brain_block_hard_blocks_chain():
    p = payload()
    p.links[3].risk_brain_blocked = True
    service = ExecutionAuthorizationChainVerificationService()
    record = service.create(p)
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_protected_operation_hard_blocks():
    service = ExecutionAuthorizationChainVerificationService()
    record = service.create(payload(expected_operation="trade-execute"))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_replay_and_workspace_isolation():
    service = ExecutionAuthorizationChainVerificationService()
    record = service.create(payload())
    service.act(record.record_id, action("verify", "same-op"))
    with pytest.raises(ValueError, match="replay"):
        service.act(record.record_id, action("approve", "same-op"))
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = ExecutionAuthorizationChainVerificationService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
