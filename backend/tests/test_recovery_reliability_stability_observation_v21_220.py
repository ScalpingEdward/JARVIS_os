from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.recovery_reliability_stability_observation_v21_220 import (
    ConsumerStabilityObservation,
    StabilityObservationRequest,
)
from app.services.recovery_reliability_stability_observation_v21_220 import (
    evaluate_episode_stability,
    reset_seen_sources_for_tests,
)

NOW = datetime(2026, 7, 29, 22, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_sources_for_tests()


def obs(cid, **kw):
    data = dict(
        consumer_id=cid,
        workspace_id='ws-1',
        baseline_id='base-a',
        baseline_version=11,
        baseline_digest='dig-11',
        recovery_sequence_digest='seq-218',
        observed_at=NOW - timedelta(seconds=30),
        healthy=True,
        dependency_satisfied=True,
        latency_quality=0.96,
        error_quality=0.96,
        recovery_quality=0.96,
        confidence=0.96,
    )
    data.update(kw)
    return ConsumerStabilityObservation(**data)


def req(**kw):
    data = dict(
        source_id='completed-219-a',
        source_state='completed',
        source_human_approved=True,
        workspace_id='ws-1',
        baseline_id='base-a',
        baseline_version=11,
        baseline_digest='dig-11',
        recovery_sequence_digest='seq-218',
        expected_consumers=['c1', 'c2'],
        observations=[obs('c1'), obs('c2')],
        now=NOW,
    )
    data.update(kw)
    return StabilityObservationRequest(**data)


def test_requires_human_approval_to_close():
    assert evaluate_episode_stability(req()).state == 'review-required'
    assert evaluate_episode_stability(req(), human_approved=True).state == 'closed'


def test_unhealthy_consumer_forces_degraded():
    d = evaluate_episode_stability(req(observations=[obs('c1'), obs('c2', healthy=False)]))
    assert d.state == 'degraded'


def test_dependency_failure_forces_degraded():
    d = evaluate_episode_stability(req(observations=[obs('c1'), obs('c2', dependency_satisfied=False)]))
    assert d.state == 'degraded'


def test_missing_observation_is_degraded():
    assert evaluate_episode_stability(req(observations=[obs('c1')])).state == 'degraded'


def test_stale_observation_is_degraded():
    stale = obs('c2', observed_at=NOW - timedelta(hours=1))
    assert evaluate_episode_stability(req(observations=[obs('c1'), stale])).state == 'degraded'


def test_recovery_sequence_mismatch_is_degraded():
    bad = obs('c2', recovery_sequence_digest='wrong-seq')
    assert evaluate_episode_stability(req(observations=[obs('c1'), bad])).state == 'degraded'


def test_low_episode_score_is_degraded():
    low = obs('c2', latency_quality=0.80, error_quality=0.80, recovery_quality=0.80, confidence=0.80)
    assert evaluate_episode_stability(req(observations=[obs('c1'), low])).state == 'degraded'


def test_unexpected_consumer_blocks():
    assert evaluate_episode_stability(req(observations=[obs('c1'), obs('c2'), obs('c3')])).state == 'blocked'


def test_duplicate_source_blocks_after_close():
    assert evaluate_episode_stability(req(), human_approved=True).state == 'closed'
    assert evaluate_episode_stability(req(), human_approved=True).state == 'blocked'


def test_risk_brain_hard_block():
    assert evaluate_episode_stability(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'
