from app.services.recovery_reliability_adoption_consistency import (
    ConsumerAdoptionObservation,
    RecoveryReliabilityAdoptionConsistencyGovernance,
    RecoveryReliabilityConsistencyRecord,
)


def obs(consumer, receipt, **kw):
    data = dict(
        consumer_id=consumer,
        workspace_id="w1",
        baseline_id="b1",
        baseline_version=5,
        baseline_digest="digest",
        receipt_digest=receipt,
        healthy=True,
    )
    data.update(kw)
    return ConsumerAdoptionObservation(**data)


def record(observations=None, **kw):
    data = dict(
        record_id="r1",
        workspace_id="w1",
        source_record_id="s1",
        baseline_id="b1",
        baseline_version=5,
        baseline_digest="digest",
        expected_consumers=("c1", "c2"),
        observations=observations or (obs("c1", "rct1"), obs("c2", "rct2")),
    )
    data.update(kw)
    return RecoveryReliabilityConsistencyRecord(**data)


def test_clean_consistency_requires_human_approval():
    g = RecoveryReliabilityAdoptionConsistencyGovernance()
    r = g.observe(record(), source_state="adopted", source_human_approved=True)
    assert r.state == "review-required"
    assert r.consistency_score == 1.0
    assert g.approve_consistency("r1", actor="human", human_approved=True).state == "consistent"


def test_missing_consumer_detects_drift():
    g = RecoveryReliabilityAdoptionConsistencyGovernance()
    r = g.observe(record(observations=(obs("c1", "rct1"),)), source_state="adopted", source_human_approved=True)
    assert r.state == "drift-detected"
    assert "missing:c2" in r.drift_reasons


def test_baseline_mismatch_detects_drift():
    g = RecoveryReliabilityAdoptionConsistencyGovernance()
    observations = (obs("c1", "rct1"), obs("c2", "rct2", baseline_version=4))
    assert g.observe(record(observations=observations), source_state="adopted", source_human_approved=True).state == "drift-detected"


def test_unhealthy_consumer_detects_drift():
    g = RecoveryReliabilityAdoptionConsistencyGovernance()
    observations = (obs("c1", "rct1"), obs("c2", "rct2", healthy=False))
    assert g.observe(record(observations=observations), source_state="adopted", source_human_approved=True).state == "drift-detected"


def test_duplicate_receipt_fails_closed():
    g = RecoveryReliabilityAdoptionConsistencyGovernance()
    observations = (obs("c1", "same"), obs("c2", "same"))
    assert g.observe(record(observations=observations), source_state="adopted", source_human_approved=True).state == "blocked"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityAdoptionConsistencyGovernance()
    assert g.observe(record(), source_state="receipt-required", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityAdoptionConsistencyGovernance()
    assert g.observe(record(risk_brain_blocked=True), source_state="adopted", source_human_approved=True).state == "blocked"
