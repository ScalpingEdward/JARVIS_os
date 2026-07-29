from app.services.recovery_reliability_baseline_adoption import (
    AdoptionReceipt,
    RecoveryReliabilityAdoptionRecord,
    RecoveryReliabilityBaselineAdoptionGovernance,
)


def record(**kw):
    data = dict(
        record_id="r1", workspace_id="w1", source_record_id="s1", consumer_id="c1",
        baseline_id="b1", baseline_version=5, baseline_digest="digest",
        rollback_version=4, rollback_value=0.72,
    )
    data.update(kw)
    return RecoveryReliabilityAdoptionRecord(**data)


def receipt(**kw):
    data = dict(
        consumer_id="c1", workspace_id="w1", baseline_id="b1", baseline_version=5,
        baseline_digest="digest", adoption_nonce="n1", adopted=True,
    )
    data.update(kw)
    return AdoptionReceipt(**data)


def test_clean_adoption_lifecycle():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    r = g.create(record(), source_state="staged", source_human_approved=True)
    assert r.state == "review-required"
    assert g.authorize("r1", actor="human", human_approved=True).state == "authorized"
    assert g.require_receipt("r1").state == "receipt-required"
    assert g.verify_receipt("r1", receipt()).state == "adopted"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    assert g.create(record(), source_state="eligible", source_human_approved=True).state == "blocked"


def test_receipt_mismatch_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    g.create(record(), source_state="staged", source_human_approved=True)
    g.authorize("r1", actor="human", human_approved=True)
    g.require_receipt("r1")
    assert g.verify_receipt("r1", receipt(baseline_version=4)).state == "blocked"


def test_replayed_nonce_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    g.nonces.add("n1")
    g.create(record(), source_state="staged", source_human_approved=True)
    g.authorize("r1", actor="human", human_approved=True)
    g.require_receipt("r1")
    assert g.verify_receipt("r1", receipt()).state == "blocked"


def test_rollback_binding_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    assert g.create(record(rollback_version=3), source_state="staged", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    assert g.create(record(risk_brain_blocked=True), source_state="staged", source_human_approved=True).state == "blocked"
