from app.services.recovery_reliability_recovery_receipt_reconciliation import (
    RecoveryCompletionRecord,
    RecoveryReceipt,
    RecoveryReliabilityReceiptReconciliationGovernance,
)


def receipt(consumer: str, nonce: str, **kw):
    data = dict(
        consumer_id=consumer,
        workspace_id="w1",
        baseline_id="b1",
        baseline_version=9,
        baseline_digest="digest",
        recovery_nonce=nonce,
        recovery_score=0.95,
        recovered=True,
        healthy=True,
        evidence_age_seconds=30,
    )
    data.update(kw)
    return RecoveryReceipt(**data)


def record(receipts=None, **kw):
    data = dict(
        record_id="r1",
        workspace_id="w1",
        source_record_id="s1",
        baseline_id="b1",
        baseline_version=9,
        baseline_digest="digest",
        expected_consumers=("c1", "c2"),
        receipts=receipts or (receipt("c1", "n1"), receipt("c2", "n2")),
    )
    data.update(kw)
    return RecoveryCompletionRecord(**data)


def test_complete_reconciliation_requires_human_close():
    g = RecoveryReliabilityReceiptReconciliationGovernance()
    r = g.reconcile(record(), source_state="recovery-ready", source_human_approved=True)
    assert r.state == "review-required"
    assert r.completion_score == 1.0
    assert g.approve_completion("r1", actor="human", human_approved=True).state == "completed"


def test_missing_consumer_is_incomplete():
    g = RecoveryReliabilityReceiptReconciliationGovernance()
    r = g.reconcile(record(receipts=(receipt("c1", "n1"),)), source_state="recovery-ready", source_human_approved=True)
    assert r.state == "incomplete"
    assert r.completion_score == 0.5


def test_stale_receipt_is_incomplete():
    g = RecoveryReliabilityReceiptReconciliationGovernance(max_evidence_age_seconds=60)
    rs = (receipt("c1", "n1"), receipt("c2", "n2", evidence_age_seconds=61))
    assert g.reconcile(record(receipts=rs), source_state="recovery-ready", source_human_approved=True).state == "incomplete"


def test_low_recovery_score_is_incomplete():
    g = RecoveryReliabilityReceiptReconciliationGovernance(min_recovery_score=0.8)
    rs = (receipt("c1", "n1"), receipt("c2", "n2", recovery_score=0.6))
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
