import pytest

from app.schemas.failover_outcome_recovery import FailoverOutcomeEvidence, FailoverRecoveryCreate, FailoverRecoveryState
from app.services.failover_outcome_recovery import FailoverOutcomeRecoveryService


def payload(**overrides):
    data=dict(
        workspace_id="ws-1",source_key="src-1",requested_by="human",
        failover_attestation_id="att-1",failover_attestation_digest="attestation-digest",
        dispatch_plan_id="plan-1",dispatch_plan_digest="dispatch-plan-digest",
        operation="read-status",target="https://example.test/status",
        primary_adapter_id="adapter-primary",primary_worker_id="worker-primary",
        standby_adapter_id="adapter-standby",standby_worker_id="worker-standby",
        evidence=FailoverOutcomeEvidence(
            completion_attested=True,side_effect_safe=True,receipt_reconciled=True,standby_stable=True,
            primary_available=True,primary_latency_ms=120,primary_health=.98,primary_receipt_reconciliation=.99,
            confidence=.98,freshness=.99,
        ),
    )
    data.update(overrides)
    return FailoverRecoveryCreate(**data)


def test_clean_failover_outcome_can_reach_recovery_ready():
    s=FailoverOutcomeRecoveryService(); r=s.create(payload())
    assert r.state==FailoverRecoveryState.EVIDENCE_READY
    r=s.act("ws-1",r.record_id,"submit-review","reviewer","op-1")
    r=s.act("ws-1",r.record_id,"approve","human","op-2")
    r=s.act("ws-1",r.record_id,"mark-recovery-ready","human","op-3")
    assert r.state==FailoverRecoveryState.RECOVERY_READY
    assert r.scores.failover_trust>.9
    assert r.scores.primary_recovery_readiness>.9


def test_unhealthy_primary_requires_hold():
    e=payload().evidence.model_copy(update={"primary_available":False,"primary_health":.3})
    s=FailoverOutcomeRecoveryService(); r=s.create(payload(evidence=e))
    r=s.act("ws-1",r.record_id,"submit-review","reviewer","op-1")
    r=s.act("ws-1",r.record_id,"approve","human","op-2")
    with pytest.raises(ValueError,match="thresholds"):
        s.act("ws-1",r.record_id,"mark-recovery-ready","human","op-3")


def test_prohibited_side_effect_degrades_failover_trust():
    e=payload().evidence.model_copy(update={"side_effect_safe":False})
    s=FailoverOutcomeRecoveryService(); r=s.create(payload(evidence=e))
    assert "side-effect-safety-failed" in r.findings
    assert r.scores.failover_trust<.9


def test_risk_brain_hard_block():
    s=FailoverOutcomeRecoveryService(); r=s.create(payload(operation="trade-execute"))
    assert r.state==FailoverRecoveryState.BLOCKED
    with pytest.raises(ValueError,match="risk brain hard block"):
        s.act("ws-1",r.record_id,"submit-review","human","op-1")


def test_replay_protection():
    s=FailoverOutcomeRecoveryService(); r=s.create(payload())
    s.act("ws-1",r.record_id,"submit-review","human","same-op")
    with pytest.raises(ValueError,match="replay"):
        s.act("ws-1",r.record_id,"hold","human","same-op")


def test_workspace_isolation():
    s=FailoverOutcomeRecoveryService(); r=s.create(payload())
    with pytest.raises(KeyError):
        s.get("ws-2",r.record_id)


def test_duplicate_source_key_is_rejected():
    s=FailoverOutcomeRecoveryService(); s.create(payload())
    with pytest.raises(ValueError,match="duplicate source_key"):
        s.create(payload())
