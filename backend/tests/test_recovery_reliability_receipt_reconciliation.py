from app.services.recovery_reliability_receipt_reconciliation import (
    RecoveryReliabilityCompletionRecord,
    RecoveryReliabilityReceipt,
    RecoveryReliabilityReceiptReconciliationGovernance,
)


def receipt(consumer, nonce, **overrides):
    data = dict(
        consumer_id=consumer,
        workspace_id="w1",
        baseline_id="b1",
        baseline_version=5,
        baseline_digest="digest",
        recovery_nonce=nonce,
        recovered=True,
        healthy=True,
        recovery_score=0.95,
        evidence_digest=f"e-{consumer}",
    )
    data.update(overrides)
    return RecoveryReliabilityReceipt(**data)


def record(receipts=None, **overrides):
    data = dict(
        record_id="r1",
        workspace_id="w1",
        source_record_id="s1",
        baseline_id="b1",
        baseline_version=5,
        baseline_digest="digest",
        expected_consumers=("c1", "c2"),
        receipts=receipts or (receipt("c1", "n1"), receipt("c2", "n2")),
    )
    data.update(overrides)
    return RecoveryReliabilityCompletionRecord(**data)


def test_complete_receipts_require_human_completion():
    g = RecoveryReliabilityReceiptReconciliationGovernance()
    r = g.reconcile(record(), source_state="recovery-ready", source_human_approved=True)
    assert r.state == "review-required"
    assert r.completion_score == 1.0
    assert g.approve_completion("r1", actor="human", human_approved=True).state == "completed"


def test_missing_consumer_stays_incomplete():
    g = RecoveryReliabilityReceiptReconciliationGovernance()
    r = g.reconcile(record(receipts=(receipt("c1", "n1"),)), source_state="recovery-ready", source_human_approved=True)
    assert r.state == "incomplete"
    assert r.completion_score == 0.5


def test_low_recovery_score_stays_incomplete():
    g = RecoveryReliabilityReceiptReconciliationGovernance()
    rs = (receipt("c1", "n1"), receipt("c2", "n2", recovery_score=0.4))
    assert g.reconcile(record(receipts=rs), source_state="recovery-ready", source_human_approved=True).state == "incomplete"


def test_baseline_mismatch_stays_incomplete():
    g = RecoveryReliabilityReceiptReconciliationGovernance()
    rs = (receipt("c1", "n1"), receipt("c2", "n2", baseline_version=4))
    assert g.reconcile(record(receipts=rs), source_state="recovery-ready", source_human_approved=True).state == "incomplete"


def test_duplicate_nonce_fails_closed():
    g = RecoveryReliabilityReceiptReconciliationGovernance()
    rs = (receipt("c1", "same"), receipt("c2", "same"))
    assert g.reconcile(record(receipts=rs), source_state="recovery-ready", source_human_approved=True).state == "blocked"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityReceiptReconciliationGovernance()
    assert g.reconcile(record(), source_state="authorized", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityReceiptReconciliationGovernance()
    assert g.reconcile(record(risk_brain_blocked=True), source_state="recovery-ready", source_human_approved=True).state == "blocked"
