import pytest

from app.services.re_adoption_reconciliation import AdoptionReceipt, ReAdoptionReconciliationService


def sequence(**overrides):
    value = {
        "record_id": "seq-1",
        "workspace_id": "ws-1",
        "status": "recovery-ready",
        "human_approved": True,
        "risk_brain_blocked": False,
        "baseline_id": "base-1",
        "baseline_version": 3,
        "baseline_digest": "digest-3",
        "affected_consumers": ["adapter-selection", "worker-selection"],
    }
    value.update(overrides)
    return value


def receipt(consumer_id: str, **overrides):
    value = dict(
        receipt_id=f"receipt-{consumer_id}",
        consumer_id=consumer_id,
        workspace_id="ws-1",
        baseline_id="base-1",
        baseline_version=3,
        baseline_digest="digest-3",
        status="adopted",
        source_digest=f"source-{consumer_id}",
    )
    value.update(overrides)
    return AdoptionReceipt(**value)


def test_all_receipts_reconcile_then_human_completion():
    svc = ReAdoptionReconciliationService()
    rec = svc.create(
        record_id="r1",
        workspace_id="ws-1",
        recovery_sequence=sequence(),
        receipts=[receipt("adapter-selection"), receipt("worker-selection")],
        source_key="s1",
    )
    assert rec.status == "review-required"
    assert rec.reconciliation_score == 1.0
    with pytest.raises(ValueError):
        svc.approve("r1", human_approved=False)
    assert svc.approve("r1", human_approved=True).status == "completed"


def test_missing_receipt_fails_closed():
    svc = ReAdoptionReconciliationService()
    rec = svc.create(
        record_id="r2",
        workspace_id="ws-1",
        recovery_sequence=sequence(),
        receipts=[receipt("adapter-selection")],
        source_key="s2",
    )
    assert rec.status == "incomplete"
    assert rec.missing_consumers == ["worker-selection"]


def test_baseline_version_mismatch_fails_closed():
    svc = ReAdoptionReconciliationService()
    rec = svc.create(
        record_id="r3",
        workspace_id="ws-1",
        recovery_sequence=sequence(),
        receipts=[receipt("adapter-selection", baseline_version=2), receipt("worker-selection")],
        source_key="s3",
    )
    assert rec.status == "incomplete"
    assert "adapter-selection" in rec.mismatched_consumers


def test_duplicate_consumer_receipt_fails_closed():
    svc = ReAdoptionReconciliationService()
    rec = svc.create(
        record_id="r4",
        workspace_id="ws-1",
        recovery_sequence=sequence(),
        receipts=[receipt("adapter-selection"), receipt("adapter-selection", receipt_id="dup"), receipt("worker-selection")],
        source_key="s4",
    )
    assert rec.status == "incomplete"
    assert rec.duplicate_consumers == ["adapter-selection"]


def test_invalid_sequence_and_risk_block_fail_closed():
    svc = ReAdoptionReconciliationService()
    rec = svc.create(
        record_id="r5",
        workspace_id="ws-1",
        recovery_sequence=sequence(status="staged", risk_brain_blocked=True),
        receipts=[receipt("adapter-selection"), receipt("worker-selection")],
        source_key="s5",
    )
    assert rec.status == "incomplete"
    assert rec.risk_brain_blocked
    assert "sequence-not-recovery-ready" in rec.findings
    assert "risk-brain-hard-block" in rec.findings


def test_workspace_isolation_and_replay_protection():
    svc = ReAdoptionReconciliationService()
    svc.create(
        record_id="r6",
        workspace_id="ws-1",
        recovery_sequence=sequence(),
        receipts=[receipt("adapter-selection"), receipt("worker-selection")],
        source_key="same",
    )
    with pytest.raises(ValueError):
        svc.create(
            record_id="r7",
            workspace_id="ws-1",
            recovery_sequence=sequence(),
            receipts=[receipt("adapter-selection"), receipt("worker-selection")],
            source_key="same",
        )
    rec = svc.create(
        record_id="r8",
        workspace_id="ws-2",
        recovery_sequence=sequence(),
        receipts=[receipt("adapter-selection", workspace_id="ws-2"), receipt("worker-selection", workspace_id="ws-2")],
        source_key="same",
    )
    assert rec.status == "incomplete"
    assert "workspace-mismatch" in rec.findings
