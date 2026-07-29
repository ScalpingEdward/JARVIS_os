from datetime import datetime, timedelta, timezone
import pytest
from app.schemas.recovery_reliability_stability_observation_v21_210 import ConsumerStabilityObservation, StabilityObservationRequest
from app.services.recovery_reliability_stability_observation_v21_210 import evaluate_stability, reset_seen_sources_for_tests

NOW = datetime(2026, 7, 29, 20, 0, tzinfo=timezone.utc)

@pytest.fixture(autouse=True)
def reset_seen(): reset_seen_sources_for_tests()

def obs(cid, **kw):
    data=dict(consumer_id=cid, workspace_id='ws-1', baseline_id='base-a', baseline_version=10, baseline_digest='dig-10', observed_at=NOW-timedelta(seconds=30), healthy=True, dependency_satisfied=True, latency_quality=0.95, error_quality=0.95, confidence=0.95)
    data.update(kw); return ConsumerStabilityObservation(**data)

def req(**kw):
    data=dict(source_id='completed-209-a', source_state='completed', source_human_approved=True, workspace_id='ws-1', baseline_id='base-a', baseline_version=10, baseline_digest='dig-10', expected_consumers=['c1','c2'], observations=[obs('c1'),obs('c2')], now=NOW)
    data.update(kw); return StabilityObservationRequest(**data)

def test_requires_human_approval_to_close():
    assert evaluate_stability(req()).state == 'review-required'
    assert evaluate_stability(req(), human_approved=True).state == 'closed'

def test_unhealthy_consumer_forces_degraded_even_with_high_scores():
    d=evaluate_stability(req(observations=[obs('c1'),obs('c2', healthy=False)]))
    assert d.state == 'degraded'

def test_dependency_failure_forces_degraded():
    assert evaluate_stability(req(observations=[obs('c1'),obs('c2', dependency_satisfied=False)])).state == 'degraded'

def test_missing_observation_is_degraded():
    assert evaluate_stability(req(observations=[obs('c1')])).state == 'degraded'

def test_stale_observation_is_degraded():
    assert evaluate_stability(req(observations=[obs('c1'),obs('c2', observed_at=NOW-timedelta(hours=1))])).state == 'degraded'

def test_lineage_mismatch_is_degraded():
    assert evaluate_stability(req(observations=[obs('c1'),obs('c2', baseline_version=9)])).state == 'degraded'

def test_unexpected_consumer_blocks():
    assert evaluate_stability(req(observations=[obs('c1'),obs('c2'),obs('c3')])).state == 'blocked'

def test_duplicate_source_blocks_after_close():
    assert evaluate_stability(req(), human_approved=True).state == 'closed'
    assert evaluate_stability(req(), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_stability(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'
