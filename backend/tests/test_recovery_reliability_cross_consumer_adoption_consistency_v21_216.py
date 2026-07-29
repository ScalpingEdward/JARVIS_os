from datetime import datetime, timedelta, timezone
import pytest
from app.schemas.recovery_reliability_cross_consumer_adoption_consistency_v21_216 import AdoptionObservation, CrossConsumerAdoptionConsistencyRequest
from app.services.recovery_reliability_cross_consumer_adoption_consistency_v21_216 import evaluate_adoption_consistency, reset_seen_sources_for_tests

NOW = datetime(2026, 7, 29, 21, 30, tzinfo=timezone.utc)

@pytest.fixture(autouse=True)
def reset_seen(): reset_seen_sources_for_tests()

def obs(cid, **kw):
    data=dict(consumer_id=cid, workspace_id='ws-1', baseline_id='base-a', baseline_version=12, baseline_digest='dig-12', receipt_nonce='r-'+cid, observation_nonce='o-'+cid, observed_at=NOW-timedelta(seconds=30), adopted=True, healthy=True, confidence=0.95)
    data.update(kw); return AdoptionObservation(**data)

def req(**kw):
    data=dict(source_id='adopted-215-a', source_state='adopted', source_human_approved=True, workspace_id='ws-1', baseline_id='base-a', baseline_version=12, baseline_digest='dig-12', expected_consumers=['c1','c2'], observations=[obs('c1'),obs('c2')], now=NOW)
    data.update(kw); return CrossConsumerAdoptionConsistencyRequest(**data)

def test_requires_human_approval_for_consistent():
    assert evaluate_adoption_consistency(req()).state == 'review-required'
    assert evaluate_adoption_consistency(req(), human_approved=True).state == 'consistent'

def test_missing_consumer_detects_drift():
    d=evaluate_adoption_consistency(req(observations=[obs('c1')]))
    assert d.state == 'drift-detected' and d.drifted_consumers == ['c2']

def test_unhealthy_or_unadopted_detects_drift():
    assert evaluate_adoption_consistency(req(observations=[obs('c1'),obs('c2', healthy=False)])).state == 'drift-detected'
    assert evaluate_adoption_consistency(req(observations=[obs('c1'),obs('c2', adopted=False)])).state == 'drift-detected'

def test_stale_or_lineage_mismatch_detects_drift():
    assert evaluate_adoption_consistency(req(observations=[obs('c1'),obs('c2', observed_at=NOW-timedelta(hours=1))])).state == 'drift-detected'
    assert evaluate_adoption_consistency(req(observations=[obs('c1'),obs('c2', baseline_version=11)])).state == 'drift-detected'

def test_duplicate_nonces_block():
    assert evaluate_adoption_consistency(req(observations=[obs('c1', receipt_nonce='same'),obs('c2', receipt_nonce='same')])).state == 'blocked'
    assert evaluate_adoption_consistency(req(observations=[obs('c1', observation_nonce='same'),obs('c2', observation_nonce='same')])).state == 'blocked'

def test_unexpected_consumer_blocks():
    assert evaluate_adoption_consistency(req(observations=[obs('c1'),obs('c2'),obs('c3')])).state == 'blocked'

def test_duplicate_source_blocks_after_consistent():
    assert evaluate_adoption_consistency(req(), human_approved=True).state == 'consistent'
    assert evaluate_adoption_consistency(req(), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_adoption_consistency(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'
