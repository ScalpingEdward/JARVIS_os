from app.services.recovery_reliability_baseline_adoption_v21_195 import (
    AdoptionReceipt,
    BaselineAdoptionRecord,
    RecoveryReliabilityBaselineAdoptionGovernance,
)


def record(**kw):
    data = dict(
        record_id="r1",
        workspace_id="w1",
        source_record_id="s1",
        consumer_id="c1",
        baseline_id="b1",
        baseline_version=8,
        baseline_digest="digest8",
        rollback_version=7,
        rollback_value=0.82,
    )
    data.update(kw)
    return BaselineAdoptionRecord(**data)


def receipt(**kw):
    data = dict(
        consumer_id="c1",
        workspace_id="w1",
        baseline_id="b1",
        baseline_version=8,
        baseline_digest="digest8",
        adoption_nonce="n1",
        evidence_age_seconds=30,
        adopted=True,
    )
    data.update(kw)
    return AdoptionReceipt(**data)


def test_clean_adoption_lifecycle():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    r = g.create(record(), source_state="staged", source_human_approved=True)
    assert r.state == "review-required"
    assert g.authorize("r1", actor="human", human_approved=True).state == "authorized"
    assert g.require_receipt("r1").state == "receipt-required"
    assert g.reconcile_receipt("r1", receipt()).state == "adopted"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    assert g.create(record(), source_state="eligible", source_human_approved=True).state == "blocked"


def test_stale_receipt_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance(max_receipt_age_seconds=300)
    g.create(record(), source_state="staged", source_human_approved=True)
    g.authorize("r1", actor="human", human_approved=True)
    g.require_receipt("r1")
    assert g.reconcile_receipt("r1", receipt(evidence_age_seconds=301)).state == "blocked"


def test_mismatched_receipt_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    g.create(record(), source_state="staged", source_human_approved=True)
    g.authorize("r1", actor="human", human_approved=True)
    g.require_receipt("r1")
    assert g.reconcile_receipt("r1", receipt(baseline_version=7)).state == "blocked"


def test_nonce_replay_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    g.create(record(), source_state="staged", source_human_approved=True)
    g.authorize("r1", actor="human", human_approved=True)
    g.require_receipt("r1")
    assert g.reconcile_receipt("r1", receipt()).state == "adopted"
    r2 = record(record_id="r2", source_record_id="s2")
    g.create(r2, source_state="staged", source_human_approved=True)
    g.authorize("r2", actor="human", human_approved=True)
    g.require_receipt("r2")
    assert g.reconcile_receipt("r2", receipt()).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    assert g.create(record(risk_brain_blocked=True), source_state="staged", source_human_approved=True).state == "blocked"
