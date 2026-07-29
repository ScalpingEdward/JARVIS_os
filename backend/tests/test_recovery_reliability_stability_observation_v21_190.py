from app.services.recovery_reliability_stability_observation_v21_190 import (
    RecoveryReliabilityStabilityObservationGovernance,
    RecoveryStabilityRecord,
    StabilityObservation,
)


def obs(consumer: str, **kw):
    data = dict(
        consumer_id=consumer,
        workspace_id="w1",
        baseline_id="b1",
        baseline_version=7,
        baseline_digest="digest",
        healthy=True,
        dependency_satisfied=True,
        latency_quality=0.95,
        error_quality=0.96,
        confidence=0.94,
        freshness=0.98,
    )
    data.update(kw)
    return StabilityObservation(**data)


def record(observations=None, **kw):
    data = dict(
        record_id="r1",
        workspace_id="w1",
        source_record_id="s1",
        baseline_id="b1",
        baseline_version=7,
        baseline_digest="digest",
        expected_consumers=("c1", "c2"),
        observations=observations or (obs("c1"), obs("c2")),
    )
    data.update(kw)
    return RecoveryStabilityRecord(**data)


def test_clean_observation_requires_human_close():
    g = RecoveryReliabilityStabilityObservationGovernance()
    r = g.observe(record(), source_state="completed", source_human_approved=True)
    assert r.state == "review-required"
    assert r.stability_score >= 0.85
    assert g.close("r1", actor="human", human_approved=True).state == "closed"


def test_unhealthy_consumer_degrades():
    g = RecoveryReliabilityStabilityObservationGovernance()
    r = g.observe(record(observations=(obs("c1"), obs("c2", healthy=False))), source_state="completed", source_human_approved=True)
    assert r.state == "degraded"


def test_missing_consumer_fails_closed():
    g = RecoveryReliabilityStabilityObservationGovernance()
    r = g.observe(record(observations=(obs("c1"),)), source_state="completed", source_human_approved=True)
    assert r.state == "blocked"


def test_baseline_mismatch_fails_closed():
    g = RecoveryReliabilityStabilityObservationGovernance()
    r = g.observe(record(observations=(obs("c1"), obs("c2", baseline_version=6))), source_state="completed", source_human_approved=True)
    assert r.state == "blocked"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityStabilityObservationGovernance()
    assert g.observe(record(), source_state="recovery-ready", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityStabilityObservationGovernance()
    assert g.observe(record(risk_brain_blocked=True), source_state="completed", source_human_approved=True).state == "blocked"
