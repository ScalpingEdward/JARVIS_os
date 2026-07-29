from datetime import datetime, timedelta, timezone
import pytest
from app.schemas.recovery_reliability_baseline_adoption_v21_205 import BaselineAdoptionRequest, BaselineAdoptionReceipt
from app.services.recovery_reliability_baseline_adoption_v21_205 import evaluate_adoption, reset_seen_for_tests

NOW = datetime(2026, 7, 29, 19, 30, tzinfo=timezone.utc)

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_for_tests()

def req(**kw):
    data = dict(source_id='rollout-204-a', source_state='staged', source_human_approved=True, workspace_id='ws-1', consumer_id='c1', baseline_id='base-a', baseline_version=9, baseline_digest='dig-9', rollback_version=8, rollback_value=0.72, now=NOW)
    data.update(kw)
    return BaselineAdoptionRequest(**data)

def receipt(**kw):
    data = dict(consumer_id='c1', workspace_id='ws-1', baseline_id='base-a', baseline_version=9, baseline_digest='dig-9', rollback_version=8, rollback_value=0.72, nonce='nonce-1', observed_at=NOW-timedelta(seconds=30), adopted=True, healthy=True, confidence=0.95)
    data.update(kw)
    return BaselineAdoptionReceipt(**data)

def test_authorization_and_receipt_lifecycle():
    assert evaluate_adoption(req()).state == 'review-required'
    assert evaluate_adoption(req(), authorized=True).state == 'receipt-required'
    assert evaluate_adoption(req(), authorized=True, receipt=receipt()).state == 'authorized'
    assert evaluate_adoption(req(), authorized=True, receipt=receipt(), receipt_human_approved=True).state == 'adopted'

def test_invalid_source_blocks():
    assert evaluate_adoption(req(source_state='eligible'), authorized=True).state == 'blocked'

def test_stale_receipt_blocks():
    r = receipt(observed_at=NOW-timedelta(hours=1))
    assert evaluate_adoption(req(), authorized=True, receipt=r, receipt_human_approved=True).state == 'blocked'

def test_lineage_mismatch_blocks():
    assert evaluate_adoption(req(), authorized=True, receipt=receipt(baseline_version=8), receipt_human_approved=True).state == 'blocked'

def test_unhealthy_or_low_confidence_blocks():
    assert evaluate_adoption(req(), authorized=True, receipt=receipt(healthy=False), receipt_human_approved=True).state == 'blocked'
    assert evaluate_adoption(req(), authorized=True, receipt=receipt(confidence=0.2), receipt_human_approved=True).state == 'blocked'

def test_duplicate_source_consumer_blocks_after_adoption():
    assert evaluate_adoption(req(), authorized=True, receipt=receipt(), receipt_human_approved=True).state == 'adopted'
    assert evaluate_adoption(req(), authorized=True, receipt=receipt(nonce='nonce-2'), receipt_human_approved=True).state == 'blocked'

def test_replayed_nonce_blocks():
    assert evaluate_adoption(req(), authorized=True, receipt=receipt(), receipt_human_approved=True).state == 'adopted'
    other = req(source_id='rollout-204-b', consumer_id='c2')
    r = receipt(consumer_id='c2')
    assert evaluate_adoption(other, authorized=True, receipt=r, receipt_human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_adoption(req(risk_brain_hard_block=True), authorized=True).state == 'blocked'
