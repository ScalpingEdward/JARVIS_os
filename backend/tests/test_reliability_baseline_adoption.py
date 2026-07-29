from app.services.reliability_baseline_adoption import (
    AdoptionReceipt,
    ReliabilityBaselineAdoptionGovernance,
    ReliabilityBaselineAdoptionRecord,
)


def record(**overrides):
    data = dict(
        record_id="r1", workspace_id="w1", source_record_id="s1", consumer_id="c1",
        baseline_id="b1", baseline_version=4, baseline_digest="abc", source_stage=1,
    )
    data.update(overrides)
    return ReliabilityBaselineAdoptionRecord(**data)


def receipt(**overrides):
    data = dict(
        consumer_id="c1", workspace_id="w1", baseline_id="b1", baseline_version=4,
        baseline_digest="abc", status="adopted", receipt_nonce="n1",
    )
    data.update(overrides)
    return AdoptionReceipt(**data)


def test_clean_authorization_and_receipt_lifecycle():
    g = ReliabilityBaselineAdoptionGovernance()
    r = g.create(record(), source_state="staged", source_stage_approved=True)
    assert r.state == "review-required"
    assert g.authorize("r1", actor="human", human_approved=True).state == "receipt-required"
    assert g.submit_receipt("r1", receipt()).state == "adopted"


def test_invalid_source_fails_closed():
    g = ReliabilityBaselineAdoptionGovernance()
    assert g.create(record(), source_state="eligible", source_stage_approved=True).state == "blocked"


def test_receipt_mismatch_fails_closed():
    g = ReliabilityBaselineAdoptionGovernance()
    g.create(record(), source_state="staged", source_stage_approved=True)
    g.authorize("r1", actor="human", human_approved=True)
    assert g.submit_receipt("r1", receipt(baseline_version=3)).state == "blocked"


def test_receipt_replay_fails_closed():
    g = ReliabilityBaselineAdoptionGovernance()
    g.create(record(record_id="r1", consumer_id="c1"), source_state="staged", source_stage_approved=True)
    g.authorize("r1", actor="human", human_approved=True)
    assert g.submit_receipt("r1", receipt(consumer_id="c1", receipt_nonce="same")).state == "adopted"
    g.create(record(record_id="r2", consumer_id="c2"), source_state="staged", source_stage_approved=True)
    g.authorize("r2", actor="human", human_approved=True)
    assert g.submit_receipt("r2", receipt(consumer_id="c2", receipt_nonce="same")).state == "blocked"


def test_risk_brain_block_propagates():
    g = ReliabilityBaselineAdoptionGovernance()
    assert g.create(record(risk_brain_blocked=True), source_state="staged", source_stage_approved=True).state == "blocked"
