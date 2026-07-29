from app.services.reliability_recovery_stability import (
    ConsumerObservation,
    RecoveryStabilityRecord,
    ReliabilityRecoveryStabilityGovernance,
)


def obs(consumer, **kw):
    data = dict(
        consumer_id=consumer, workspace_id="w1", baseline_id="b1", baseline_version=4,
        baseline_digest="digest", healthy=True, dependency_satisfaction=0.95,
        latency_quality=0.95, error_quality=0.95, confidence=0.95, freshness=0.95,
    )
    data.update(kw)
    return ConsumerObservation(**data)


def record(observations=None, **kw):
    data = dict(
        record_id="r1", workspace_id="w1", source_record_id="s1", baseline_id="b1",
        baseline_version=4, baseline_digest="digest", expected_consumers=("c1", "c2"),
        observations=observations or (obs("c1"), obs("c2")),
    )
    data.update(kw)
    return RecoveryStabilityRecord(**data)


def test_clean_observation_requires_human_close():
    g = ReliabilityRecoveryStabilityGovernance()
    r = g.observe(record(), source_state="completed", source_human_approved=True)
    assert r.state == "review-required"
    assert r.stability_score > 0.9
    assert g.approve_closure("r1", actor="human", human_approved=True).state == "closed"


def test_drift_is_degraded():
    g = ReliabilityRecoveryStabilityGovernance()
    r = record(observations=(obs("c1"), obs("c2", baseline_version=3)))
    assert g.observe(r, source_state="completed", source_human_approved=True).state == "degraded"


def test_missing_consumer_fails_closed():
    g = ReliabilityRecoveryStabilityGovernance()
    r = record(observations=(obs("c1"),))
    assert g.observe(r, source_state="completed", source_human_approved=True).state == "blocked"


def test_low_quality_is_degraded():
    g = ReliabilityRecoveryStabilityGovernance()
    r = record(observations=(obs("c1"), obs("c2", healthy=False, confidence=0.1, freshness=0.1)))
    assert g.observe(r, source_state="completed", source_human_approved=True).state == "degraded"


def test_invalid_source_fails_closed():
    g = ReliabilityRecoveryStabilityGovernance()
    assert g.observe(record(), source_state="recovery-ready", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = ReliabilityRecoveryStabilityGovernance()
    assert g.observe(record(risk_brain_blocked=True), source_state="completed", source_human_approved=True).state == "blocked"
