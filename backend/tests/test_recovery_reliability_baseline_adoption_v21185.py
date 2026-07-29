from app.services.recovery_reliability_baseline_adoption_v21185 import (
    AdoptionReceipt,
    RecoveryReliabilityAdoptionRecord,
    RecoveryReliabilityBaselineAdoptionGovernance,
)


def record(**overrides):
    data = dict(
        record_id="r1", workspace_id="w1", source_record_id="s1", consumer_id="c1",
        baseline_id="b1", baseline_version=5, baseline_digest="digest",
        rollback_version=4, rollback_value=0.55, max_receipt_age_seconds=300,
    )
    data.update(overrides)
    return RecoveryReliabilityAdoptionRecord(**data)


def receipt(**overrides):
    data = dict(
        consumer_id="c1", workspace_id="w1", baseline_id="b1", baseline_version=5,
        baseline_digest="digest", adoption_nonce="n1", adopted=True, evidence_age_seconds=20,
    )
    data.update(overrides)
    return AdoptionReceipt(**data)


def test_clean_adoption_lifecycle():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    assert g.create(record(), source_state="staged", source_human_approved=True).state == "review-required"
    assert g.authorize("r1", actor="human", human_approved=True).state == "receipt-required"
    assert g.submit_receipt("r1", receipt()).state == "adopted"


def test_stale_receipt_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    g.create(record(), source_state="staged", source_human_approved=True)
    g.authorize("r1", actor="human", human_approved=True)
    assert g.submit_receipt("r1", receipt(evidence_age_seconds=301)).state == "blocked"


def test_replayed_nonce_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    g.create(record(), source_state="staged", source_human_approved=True)
    g.authorize("r1", actor="human", human_approved=True)
    assert g.submit_receipt("r1", receipt()).state == "adopted"
    g.create(record(record_id="r2", source_record_id="s2"), source_state="staged", source_human_approved=True)
    g.authorize("r2", actor="human", human_approved=True)
    assert g.submit_receipt("r2", receipt()).state == "blocked"


def test_lineage_mismatch_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    g.create(record(), source_state="staged", source_human_approved=True)
    g.authorize("r1", actor="human", human_approved=True)
    assert g.submit_receipt("r1", receipt(baseline_version=4)).state == "blocked"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    assert g.create(record(), source_state="eligible", source_human_approved=True).state == "blocked"


def test_risk_brain_block_fails_closed():
    g = RecoveryReliabilityBaselineAdoptionGovernance()
    assert g.create(record(risk_brain_blocked=True), source_state="staged", source_human_approved=True).state == "blocked"
