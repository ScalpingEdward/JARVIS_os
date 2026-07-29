from app.services.recovery_reliability_cross_consumer_consistency import (
    ConsumerAdoptionObservation,
    CrossConsumerConsistencyRecord,
    RecoveryReliabilityCrossConsumerConsistencyGovernance,
)


def obs(consumer, nonce, **kw):
    data = dict(consumer_id=consumer, workspace_id="w1", baseline_id="b1", baseline_version=8,
                baseline_digest="digest", receipt_nonce=nonce, receipt_age_seconds=60, healthy=True)
    data.update(kw)
    return ConsumerAdoptionObservation(**data)


def record(observations=None, **kw):
    data = dict(record_id="r1", workspace_id="w1", source_record_id="s1", baseline_id="b1",
                baseline_version=8, baseline_digest="digest", expected_consumers=("c1", "c2"),
                observations=observations or (obs("c1", "n1"), obs("c2", "n2")))
    data.update(kw)
    return CrossConsumerConsistencyRecord(**data)


def test_clean_consistency_requires_human_close():
    g = RecoveryReliabilityCrossConsumerConsistencyGovernance()
    r = g.observe(record(), source_state="adopted", source_human_approved=True)
    assert r.state == "review-required"
    assert r.consistency_score == 1.0
    assert g.approve_consistency("r1", actor="human", human_approved=True).state == "consistent"


def test_missing_consumer_detects_drift():
    g = RecoveryReliabilityCrossConsumerConsistencyGovernance()
    r = g.observe(record(observations=(obs("c1", "n1"),)), source_state="adopted", source_human_approved=True)
    assert r.state == "drift-detected"
    assert "missing-consumer:c2" in r.drift_reasons


def test_stale_receipt_detects_drift():
    g = RecoveryReliabilityCrossConsumerConsistencyGovernance()
    rs = (obs("c1", "n1"), obs("c2", "n2", receipt_age_seconds=901))
    r = g.observe(record(observations=rs), source_state="adopted", source_human_approved=True)
    assert r.state == "drift-detected"
    assert any("stale-receipt" in reason for reason in r.drift_reasons)


def test_baseline_mismatch_detects_drift():
    g = RecoveryReliabilityCrossConsumerConsistencyGovernance()
    rs = (obs("c1", "n1"), obs("c2", "n2", baseline_version=7))
    assert g.observe(record(observations=rs), source_state="adopted", source_human_approved=True).state == "drift-detected"


def test_duplicate_nonce_fails_closed():
    g = RecoveryReliabilityCrossConsumerConsistencyGovernance()
    rs = (obs("c1", "same"), obs("c2", "same"))
    assert g.observe(record(observations=rs), source_state="adopted", source_human_approved=True).state == "blocked"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityCrossConsumerConsistencyGovernance()
    assert g.observe(record(), source_state="receipt-required", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityCrossConsumerConsistencyGovernance()
    assert g.observe(record(risk_brain_blocked=True), source_state="adopted", source_human_approved=True).state == "blocked"
