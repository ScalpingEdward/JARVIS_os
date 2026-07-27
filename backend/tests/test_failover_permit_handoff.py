import pytest

from app.schemas.failover_permit_handoff import FailoverPermitAction, FailoverPermitConsume, FailoverPermitCreate, FailoverPermitState
from app.services.failover_permit_handoff import FailoverPermitHandoffService


def payload(**overrides):
    base = dict(
        workspace_id="ws-1",
        source_key="src-1",
        requested_by="planner",
        failover_authorization_id="auth-1",
        failover_authorization_digest="a" * 64,
        dispatch_plan_id="plan-1",
        dispatch_plan_digest="b" * 64,
        operation="read-fetch",
        target="https://example.com/status",
        standby_adapter_id="adapter-b",
        standby_worker_id="worker-b",
        gateway_id="gateway-1",
        sandbox_policy_digest="c" * 64,
        gateway_policy_digest="d" * 64,
        worker_policy_digest="e" * 64,
        failover_authorized=True,
    )
    base.update(overrides)
    return FailoverPermitCreate(**base)


def approve_and_issue(service, record):
    service.act("ws-1", record.permit_id, "submit-review", "reviewer", "op-1")
    service.act("ws-1", record.permit_id, "approve", "human", "op-2")
    return service.act("ws-1", record.permit_id, "issue", "human", "op-3")


def test_failover_permit_lifecycle_single_use():
    service = FailoverPermitHandoffService()
    record = service.create(payload())
    assert record.state == FailoverPermitState.AUTHORIZED
    issued = approve_and_issue(service, record)
    assert issued.state == FailoverPermitState.ISSUED
    assert issued.permit_token_digest

    consumed = service.consume(
        issued.permit_id,
        FailoverPermitConsume(
            workspace_id="ws-1",
            actor="worker-controller",
            operation_id="op-4",
            failover_authorization_digest="a" * 64,
            standby_adapter_id="adapter-b",
            standby_worker_id="worker-b",
            gateway_id="gateway-1",
        ),
    )
    assert consumed.state == FailoverPermitState.CONSUMED

    with pytest.raises(ValueError, match="permit is not issued"):
        service.consume(
            issued.permit_id,
            FailoverPermitConsume(
                workspace_id="ws-1",
                actor="worker-controller",
                operation_id="op-5",
                failover_authorization_digest="a" * 64,
                standby_adapter_id="adapter-b",
                standby_worker_id="worker-b",
                gateway_id="gateway-1",
            ),
        )


def test_failover_permit_binding_mismatch_fails_closed():
    service = FailoverPermitHandoffService()
    issued = approve_and_issue(service, service.create(payload()))
    with pytest.raises(ValueError, match="standby worker binding mismatch"):
        service.consume(
            issued.permit_id,
            FailoverPermitConsume(
                workspace_id="ws-1",
                actor="worker-controller",
                operation_id="op-4",
                failover_authorization_digest="a" * 64,
                standby_adapter_id="adapter-b",
                standby_worker_id="worker-x",
                gateway_id="gateway-1",
            ),
        )


def test_risk_brain_hard_block_for_protected_operation():
    service = FailoverPermitHandoffService()
    record = service.create(payload(operation="trade-execute"))
    assert record.state == FailoverPermitState.BLOCKED
    with pytest.raises(ValueError, match="risk brain hard block"):
        service.act("ws-1", record.permit_id, "submit-review", "reviewer", "op-1")


def test_unauthorized_failover_is_blocked():
    service = FailoverPermitHandoffService()
    record = service.create(payload(failover_authorized=False))
    assert record.state == FailoverPermitState.BLOCKED


def test_replay_workspace_isolation_and_duplicate_source():
    service = FailoverPermitHandoffService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())

    service.act("ws-1", record.permit_id, "submit-review", "reviewer", "replay-1")
    with pytest.raises(ValueError, match="operation replay detected"):
        service.act("ws-1", record.permit_id, "submit-review", "reviewer", "replay-1")

    with pytest.raises(KeyError):
        service.get("ws-2", record.permit_id)
