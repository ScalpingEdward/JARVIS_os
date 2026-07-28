import pytest

from app.services.coordinated_recovery_stability import (
    ConsumerObservation,
    CoordinatedRecoveryStabilityService,
)


def completion(**overrides):
    value = {
        "record_id": "completion-1",
        "workspace_id": "ws-1",
        "status": "completed",
        "human_approved": True,
        "risk_brain_blocked": False,
        "baseline_id": "baseline-a",
        "baseline_version": 3,
        "baseline_digest": "digest-a",
        "consumer_ids": ["c1", "c2"],
    }
    value.update(overrides)
    return value


def obs(consumer_id, **overrides):
    value = dict(
        consumer_id=consumer_id,
        health=0.95,
        baseline_match=True,
        dependency_satisfaction=0.94,
        latency_quality=0.92,
        error_quality=0.96,
        confidence=0.93,
        freshness=0.95,
    )
    value.update(overrides)
    return ConsumerObservation(**value)


def test_clean_completion_can_close_after_human_review():
    svc = CoordinatedRecoveryStabilityService()
    rec = svc.create(
        record_id="r1", workspace_id="ws-1", completion_evidence=completion(),
        observations=[obs("c1"), obs("c2")], source_key="s1",
    )
    assert rec.status == "review-required"
    with pytest.raises(ValueError):
        svc.approve("r1", human_approved=False)
    assert svc.approve("r1", human_approved=True).status == "closed"


def test_baseline_drift_fails_closed():
    svc = CoordinatedRecoveryStabilityService()
    rec = svc.create(
        record_id="r2", workspace_id="ws-1", completion_evidence=completion(),
        observations=[obs("c1"), obs("c2", baseline_match=False)], source_key="s2",
    )
    assert rec.status == "degraded"
    assert "baseline-drift-detected" in rec.findings


def test_consumer_set_mismatch_fails_closed():
    svc = CoordinatedRecoveryStabilityService()
    rec = svc.create(
        record_id="r3", workspace_id="ws-1", completion_evidence=completion(),
        observations=[obs("c1")], source_key="s3",
    )
    assert rec.status == "degraded"
    assert "consumer-set-mismatch" in rec.findings


def test_low_quality_observation_fails_closed():
    svc = CoordinatedRecoveryStabilityService()
    rec = svc.create(
        record_id="r4", workspace_id="ws-1", completion_evidence=completion(),
        observations=[obs("c1", confidence=0.3, health=0.4), obs("c2", confidence=0.3, health=0.4)],
        source_key="s4",
    )
    assert rec.status == "degraded"
    assert "confidence-below-floor" in rec.findings


def test_risk_brain_block_propagates():
    svc = CoordinatedRecoveryStabilityService()
    rec = svc.create(
        record_id="r5", workspace_id="ws-1",
        completion_evidence=completion(risk_brain_blocked=True),
        observations=[obs("c1"), obs("c2")], source_key="s5",
    )
    assert rec.risk_brain_blocked
    assert rec.status == "degraded"


def test_replay_and_workspace_isolation():
    svc = CoordinatedRecoveryStabilityService()
    svc.create(
        record_id="r6", workspace_id="ws-1", completion_evidence=completion(),
        observations=[obs("c1"), obs("c2")], source_key="same",
    )
    with pytest.raises(ValueError):
        svc.create(
            record_id="r7", workspace_id="ws-1", completion_evidence=completion(),
            observations=[obs("c1"), obs("c2")], source_key="same",
        )
    rec = svc.create(
        record_id="r8", workspace_id="ws-2", completion_evidence=completion(),
        observations=[obs("c1"), obs("c2")], source_key="same",
    )
    assert rec.status == "degraded"
    assert "workspace-mismatch" in rec.findings


def test_empty_observation_set_fails_closed():
    svc = CoordinatedRecoveryStabilityService()
    rec = svc.create(
        record_id="r9", workspace_id="ws-1", completion_evidence=completion(consumer_ids=[]),
        observations=[], source_key="s9",
    )
    assert rec.status == "degraded"
    assert "empty-observation-set" in rec.findings
