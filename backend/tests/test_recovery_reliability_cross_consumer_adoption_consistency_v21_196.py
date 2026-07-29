from app.services.recovery_reliability_cross_consumer_adoption_consistency_v21_196 import (
    AdoptionObservation,
    CrossConsumerAdoptionRecord,
    RecoveryReliabilityCrossConsumerAdoptionConsistencyGovernance,
)


def obs(consumer: str, **kw):
    data = dict(
        consumer_id=consumer,
        workspace_id="w1",
        baseline_id="b1",
        baseline_version=8,
        baseline_digest="digest",
        receipt_nonce=f"nonce-{consumer}",
        receipt_age_seconds=30,
        healthy=True,
        adopted=True,
        confidence=0.98,
    )
    data.update(kw)
    return AdoptionObservation(**data)


def record(observations=None, **kw):
    data = dict(
        record_id="r1",
        workspace_id="w1",
        source_record_id="s1",
        baseline_id="b1",
        baseline_version=8,
        baseline_digest="digest",
        expected_consumers=("c1", "c2"),
        observations=observations or (obs("c1"), obs("c2")),
    )
    data.update(kw)
    return CrossConsumerAdoptionRecord(**data)


def test_clean_adoption_set_requires_human_consistency_approval():
    g = RecoveryReliabilityCrossConsumerAdoptionConsistencyGovernance()
    r = g.observe(record(), source_state="adopted", source_human_approved=True)
    assert r.state == "review-required"
    assert r.consistency_score == 1.0
    assert g.approve_consistency("r1", actor="human", human_approved=True).state == "consistent"


def test_missing_consumer_detects_drift():
    g = RecoveryReliabilityCrossConsumerAdoptionConsistencyGovernance()
    r = g.observe(record(observations=(obs("c1"),)), source_state="adopted", source_human_approved=True)
    assert r.state == "drift-detected"
    assert "missing-consumer:c2" in r.drift_reasons


def test_stale_receipt_detects_drift():
    g = RecoveryReliabilityCrossConsumerAdoptionConsistencyGovernance()
    r = g.observe(record(observations=(obs("c1"), obs("c2", receipt_age_seconds=901))), source_state="adopted", source_human_approved=True)
    assert r.state == "drift-detected"
    assert "stale-receipt:c2" in r.drift_reasons


def test_baseline_mismatch_detects_drift():
    g = RecoveryReliabilityCrossConsumerAdoptionConsistencyGovernance()
    r = g.observe(record(observations=(obs("c1"), obs("c2", baseline_version=7))), source_state="adopted", source_human_approved=True)
    assert r.state == "drift-detected"


def test_duplicate_nonce_fails_closed():
    g = RecoveryReliabilityCrossConsumerAdoptionConsistencyGovernance()
    r = g.observe(record(observations=(obs("c1", receipt_nonce="same"), obs("c2", receipt_nonce="same"))), source_state="adopted", source_human_approved=True)
    assert r.state == "blocked"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityCrossConsumerAdoptionConsistencyGovernance()
    assert g.observe(record(), source_state="staged", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityCrossConsumerAdoptionConsistencyGovernance()
    assert g.observe(record(risk_brain_blocked=True), source_state="adopted", source_human_approved=True).state == "blocked"
