from datetime import datetime, timedelta, timezone
import pytest
from app.schemas.recovery_reliability_adoption_consistency_v21_206 import ConsumerAdoptionObservation, AdoptionConsistencyRequest
from app.services.recovery_reliability_adoption_consistency_v21_206 import evaluate_adoption_consistency, reset_seen_sources_for_tests

NOW = datetime(2026, 7, 29, 20, 0, tzinfo=timezone.utc)

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_sources_for_tests()

def obs(cid, **kw):
    data=dict(consumer_id=cid, workspace_id='ws-1', baseline_id='base-a', baseline_version=9, baseline_digest='dig-9', receipt_nonce='n-'+cid, observed_at=NOW-timedelta(seconds=20), adopted=True, healthy=True, confidence=0.95)
    data.update(kw)
    return ConsumerAdoptionObservation(**data)

def req(**kw):
    data=dict(source_id='adoption-205-a', source_state='adopted', source_human_approved=True, workspace_id='ws-1', baseline_id='base-a', baseline_version=9, baseline_digest='dig-9', expected_consumers=['c1','c2'], observations=[obs('c1'),obs('c2')], now=NOW)
    data.update(kw)
    return AdoptionConsistencyRequest(**data)

def test_requires_human_approval_for_consistent():
    assert evaluate_adoption_consistency(req()).state == 'review-required'
    assert evaluate_adoption_consistency(req(), human_approved=True).state == 'consistent'

def test_missing_consumer_detects_drift():
    d=evaluate_adoption_consistency(req(observations=[obs('c1')]))
    assert d.state == 'drift-detected' and d.drifted_consumers == ['c2']

def test_unhealthy_consumer_detects_drift():
    assert evaluate_adoption_consistency(req(observations=[obs('c1'),obs('c2', healthy=False)])).state == 'drift-detected'

def test_lineage_mismatch_detects_drift():
    assert evaluate_adoption_consistency(req(observations=[obs('c1'),obs('c2', baseline_version=8)])).state == 'drift-detected'

def test_stale_observation_detects_drift():
    assert evaluate_adoption_consistency(req(observations=[obs('c1'),obs('c2', observed_at=NOW-timedelta(hours=1))])).state == 'drift-detected'

def test_duplicate_nonce_blocks():
    assert evaluate_adoption_consistency(req(observations=[obs('c1', receipt_nonce='x'),obs('c2', receipt_nonce='x')])).state == 'blocked'

def test_unexpected_consumer_blocks():
    assert evaluate_adoption_consistency(req(observations=[obs('c1'),obs('c2'),obs('c3')])).state == 'blocked'

def test_duplicate_source_blocks_after_consistency():
    assert evaluate_adoption_consistency(req(), human_approved=True).state == 'consistent'
    assert evaluate_adoption_consistency(req(), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_adoption_consistency(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'
