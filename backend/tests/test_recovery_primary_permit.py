import pytest

from app.schemas.recovery_primary_permit import RecoveryPermitAction, RecoveryPermitConsume, RecoveryPermitCreate, RecoveryPermitState
from app.services.recovery_primary_permit import RecoveryPrimaryPermitService


def payload(**overrides):
    data = dict(
        workspace_id="ws-1", source_key="src-1", requested_by="planner",
        recovery_plan_id="rp-1", recovery_plan_digest="recovery-plan-digest",
        recovery_readiness_digest="recovery-readiness-digest", dispatch_plan_digest="dispatch-plan-digest",
        operation="read-health", target="https://example.test/health",
        primary_adapter_id="adapter-primary", primary_worker_id="worker-primary", gateway_id="gateway-1",
        sandbox_policy_digest="sandbox-policy-digest", gateway_policy_digest="gateway-policy-digest",
        worker_policy_digest="worker-policy-digest", plan_state="ready",
    )
    data.update(overrides)
    return RecoveryPermitCreate(**data)


def test_full_single_use_lifecycle():
    s = RecoveryPrimaryPermitService()
    r = s.create(payload())
    assert r.state == RecoveryPermitState.PLAN_READY
    r = s.act("ws-1", r.permit_id, "submit-review", "alice", "op-1")
    assert r.state == RecoveryPermitState.REVIEW_REQUIRED
    r = s.act("ws-1", r.permit_id, "approve", "alice", "op-2")
    assert r.state == RecoveryPermitState.APPROVED
    issued = s.act("ws-1", r.permit_id, "issue", "alice", "op-3")
    token = issued["permit_token"]
    r = issued["record"]
    assert r.state == RecoveryPermitState.ISSUED
    consumed = s.consume(r.permit_id, RecoveryPermitConsume(
        workspace_id="ws-1", actor="worker", operation_id="op-4", permit_token=token,
        recovery_plan_digest="recovery-plan-digest", primary_adapter_id="adapter-primary",
        primary_worker_id="worker-primary", gateway_id="gateway-1",
    ))
    assert consumed.state == RecoveryPermitState.CONSUMED
    with pytest.raises(ValueError, match="not issued or already consumed"):
        s.consume(r.permit_id, RecoveryPermitConsume(
            workspace_id="ws-1", actor="worker", operation_id="op-5", permit_token=token,
            recovery_plan_digest="recovery-plan-digest", primary_adapter_id="adapter-primary",
            primary_worker_id="worker-primary", gateway_id="gateway-1",
        ))


def test_requires_ready_plan():
    s = RecoveryPrimaryPermitService()
    with pytest.raises(ValueError, match="recovery plan must be ready"):
        s.create(payload(plan_state="approved"))


def test_requires_human_approval_before_issue():
    s = RecoveryPrimaryPermitService()
    r = s.create(payload())
    with pytest.raises(ValueError, match="human approval required"):
        s.act("ws-1", r.permit_id, "issue", "alice", "op-1")


def test_identity_mismatch_fails_closed():
    s = RecoveryPrimaryPermitService()
    r = s.create(payload())
    s.act("ws-1", r.permit_id, "submit-review", "alice", "op-1")
    s.act("ws-1", r.permit_id, "approve", "alice", "op-2")
    issued = s.act("ws-1", r.permit_id, "issue", "alice", "op-3")
    with pytest.raises(ValueError, match="primary handoff identity mismatch"):
        s.consume(r.permit_id, RecoveryPermitConsume(
            workspace_id="ws-1", actor="worker", operation_id="op-4", permit_token=issued["permit_token"],
            recovery_plan_digest="recovery-plan-digest", primary_adapter_id="wrong-adapter",
            primary_worker_id="worker-primary", gateway_id="gateway-1",
        ))


def test_protected_operation_hard_block():
    s = RecoveryPrimaryPermitService()
    r = s.create(payload(operation="trade-execute"))
    assert r.state == RecoveryPermitState.BLOCKED
    with pytest.raises(ValueError, match="risk brain hard block"):
        s.act("ws-1", r.permit_id, "submit-review", "alice", "op-1")


def test_replay_workspace_and_duplicate_source_protection():
    s = RecoveryPrimaryPermitService()
    r = s.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        s.create(payload())
    s.act("ws-1", r.permit_id, "submit-review", "alice", "op-1")
    with pytest.raises(ValueError, match="operation replay"):
        s.act("ws-1", r.permit_id, "approve", "alice", "op-1")
    with pytest.raises(KeyError):
        s.get("ws-2", r.permit_id)
