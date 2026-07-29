from app.services.reliability_baseline_consistency import (
    AdoptionObservation,
    ConsistencyRecord,
    ReliabilityBaselineConsistencyGovernance,
)


def obs(cid, **overrides):
    data = dict(consumer_id=cid, baseline_id="b1", baseline_version=5, baseline_digest="dig", receipt_digest=f"r-{cid}", healthy=True)
    data.update(overrides)
    return AdoptionObservation(**data)


def record(**overrides):
    data = dict(
        record_id="r1", workspace_id="w1", source_record_id="s1", baseline_id="b1",
        baseline_version=5, baseline_digest="dig", expected_consumers=("c1", "c2"),
        observations=(obs("c1"), obs("c2")),
    )
    data.update(overrides)
    return ConsistencyRecord(**data)


def test_clean_consistency_lifecycle():
    g = ReliabilityBaselineConsistencyGovernance()
    r = g.create(record(), source_state="adopted", source_human_approved=True)
    assert r.state == "review-required"
    assert r.consistency_score == 1.0
    assert g.approve_consistency("r1", human_approved=True, actor="human").state == "consistent"


def test_version_drift_is_detected():
    g = ReliabilityBaselineConsistencyGovernance()
    r = record(observations=(obs("c1"), obs("c2", baseline_version=4)))
    out = g.create(r, source_state="adopted", source_human_approved=True)
    assert out.state == "drift-detected"
    assert out.drift_consumers == ("c2",)


def test_missing_consumer_is_drift():
    g = ReliabilityBaselineConsistencyGovernance()
    r = record(observations=(obs("c1"),))
    assert g.create(r, source_state="adopted", source_human_approved=True).state == "drift-detected"


def test_invalid_source_fails_closed():
    g = ReliabilityBaselineConsistencyGovernance()
    assert g.create(record(), source_state="receipt-required", source_human_approved=True).state == "blocked"


def test_risk_brain_block_fails_closed():
    g = ReliabilityBaselineConsistencyGovernance()
    assert g.create(record(risk_brain_blocked=True), source_state="adopted", source_human_approved=True).state == "blocked"
