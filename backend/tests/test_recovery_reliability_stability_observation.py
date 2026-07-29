from app.services.recovery_reliability_stability_observation import (
    ConsumerStabilityObservation,
    RecoveryReliabilityStabilityObservationGovernance,
    RecoveryReliabilityStabilityRecord,
)


def obs(consumer, **kw):
    data = dict(
        consumer_id=consumer, workspace_id="w1", baseline_id="b1", baseline_version=5,
        baseline_digest="digest", healthy=True, baseline_match=True,
        dependency_satisfaction=0.95, latency_quality=0.94, error_quality=0.96,
        confidence=0.93, freshness=0.97,
    )
    data.update(kw)
    return ConsumerStabilityObservation(**data)


def record(observations=None, **kw):
    data = dict(
        record_id="r1", workspace_id="w1", source_record_id="s1", baseline_id="b1",
        baseline_version=5, baseline_digest="digest", expected_consumers=("c1", "c2"),
        observations=observations or (obs("c1"), obs("c2")),
    )
    data.update(kw)
    return RecoveryReliabilityStabilityRecord(**data)


def test_clean_observation_requires_human_close():
    g = RecoveryReliabilityStabilityObservationGovernance()
    r = g.observe(record(), source_state="completed", source_human_approved=True)
    assert r.state == "review-required"
    assert r.stability_score >= r.minimum_stability_score
    assert g.approve_closure("r1", actor="human", human_approved=True).state == "closed"


def test_unhealthy_consumer_degrades():
    g = RecoveryReliabilityStabilityObservationGovernance()
    rs = (obs("c1"), obs("c2", healthy=False))
    assert g.observe(record(observations=rs), source_state="completed", source_human_approved=True).state == "degraded"


def test_missing_consumer_fails_closed():
    g = RecoveryReliabilityStabilityObservationGovernance()
    rs = (obs("c1"),)
    assert g.observe(record(observations=rs), source_state="completed", source_human_approved=True).state == "blocked"


def test_baseline_drift_degrades():
    g = RecoveryReliabilityStabilityObservationGovernance()
    rs = (obs("c1"), obs("c2", baseline_digest="other"))
    assert g.observe(record(observations=rs), source_state="completed", source_human_approved=True).state == "degraded"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityStabilityObservationGovernance()
    assert g.observe(record(), source_state="recovery-ready", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityStabilityObservationGovernance()
    assert g.observe(record(risk_brain_blocked=True), source_state="completed", source_human_approved=True).state == "blocked"
