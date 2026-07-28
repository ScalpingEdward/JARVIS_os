import pytest

from app.schemas.recovery_primary_plan import RecoveryPrimaryPlanCreate, RecoveryPreconditions, RecoveryPrimaryPlanState
from app.services.recovery_primary_plan import RecoveryPrimaryPlanService


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        source_key="source-1",
        requested_by="human-1",
        recovery_readiness_id="rr-1",
        recovery_readiness_digest="digest-recovery-ready",
        dispatch_plan_id="dp-1",
        dispatch_plan_digest="digest-dispatch-plan",
        operation="read-health",
        target="https://example.invalid/health",
        primary_adapter_id="adapter-primary",
        primary_worker_id="worker-primary",
        standby_adapter_id="adapter-standby",
        standby_worker_id="worker-standby",
        gateway_id="gateway-1",
        sandbox_policy_digest="digest-sandbox",
        gateway_policy_digest="digest-gateway",
        worker_policy_digest="digest-worker",
        preconditions=RecoveryPreconditions(
            primary_available=True,
            primary_healthy=True,
            primary_latency_ms=120,
            primary_receipt_reconciliation=.99,
            failover_path_stable=True,
            no_open_side_effect_findings=True,
            confidence=.99,
            freshness=.98,
        ),
    )
    data.update(overrides)
    return RecoveryPrimaryPlanCreate(**data)


def test_clean_recovery_plan_lifecycle():
    svc = RecoveryPrimaryPlanService()
    r = svc.create(payload())
    assert r.state == RecoveryPrimaryPlanState.DRAFT
    r = svc.act("ws-1", r.record_id, "validate-preconditions", "system", "op-1")
    assert r.state == RecoveryPrimaryPlanState.PRECONDITION_READY
    r = svc.act("ws-1", r.record_id, "submit-review", "human-1", "op-2")
    r = svc.act("ws-1", r.record_id, "approve", "human-1", "op-3")
    assert r.approved_by == "human-1"
    r = svc.act("ws-1", r.record_id, "mark-ready", "human-1", "op-4")
    assert r.state == RecoveryPrimaryPlanState.READY


def test_unhealthy_primary_fails_precondition_validation():
    svc = RecoveryPrimaryPlanService()
    pc = RecoveryPreconditions(
        primary_available=True,
        primary_healthy=False,
        primary_latency_ms=120,
        primary_receipt_reconciliation=.99,
        failover_path_stable=True,
        no_open_side_effect_findings=True,
    )
    r = svc.create(payload(preconditions=pc))
    assert "primary-unhealthy" in r.precondition_failures
    with pytest.raises(ValueError, match="preconditions"):
        svc.act("ws-1", r.record_id, "validate-preconditions", "system", "op-1")


def test_risk_brain_blocks_protected_operation():
    svc = RecoveryPrimaryPlanService()
    r = svc.create(payload(operation="trade-execute"))
    assert r.state == RecoveryPrimaryPlanState.BLOCKED
    with pytest.raises(ValueError, match="risk brain hard block"):
        svc.act("ws-1", r.record_id, "validate-preconditions", "system", "op-1")


def test_human_approval_required_before_ready():
    svc = RecoveryPrimaryPlanService()
    r = svc.create(payload())
    r = svc.act("ws-1", r.record_id, "validate-preconditions", "system", "op-1")
    r = svc.act("ws-1", r.record_id, "submit-review", "human-1", "op-2")
    with pytest.raises(ValueError):
        svc.act("ws-1", r.record_id, "mark-ready", "human-1", "op-3")


def test_replay_workspace_isolation_and_duplicate_source():
    svc = RecoveryPrimaryPlanService()
    r = svc.create(payload())
    svc.act("ws-1", r.record_id, "validate-preconditions", "system", "op-1")
    with pytest.raises(ValueError, match="replay"):
        svc.act("ws-1", r.record_id, "submit-review", "human-1", "op-1")
    with pytest.raises(KeyError):
        svc.get("ws-2", r.record_id)
    with pytest.raises(ValueError, match="duplicate source_key"):
        svc.create(payload())
