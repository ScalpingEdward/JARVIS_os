from datetime import datetime, timedelta, timezone
import pytest
from app.schemas.recovery_reliability_baseline_adoption_v21_215 import AdoptionReceipt, BaselineAdoptionRequest
from app.services.recovery_reliability_baseline_adoption_v21_215 import evaluate_baseline_adoption, reset_seen_for_tests

NOW = datetime(2026, 7, 29, 21, 10, tzinfo=timezone.utc)

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_for_tests()

def receipt(**kw):
    data=dict(consumer_id='c1', workspace_id='ws-1', baseline_id='base-new', baseline_version=11, baseline_digest='dig-11', rollback_baseline_id='base-old', rollback_version=10, nonce='nonce-1', observed_at=NOW-timedelta(seconds=30), adopted=True, healthy=True, confidence=0.95)
    data.update(kw)
    return AdoptionReceipt(**data)

def req(**kw):
    data=dict(source_id='staged-214-a', source_state='staged', source_human_approved=True, workspace_id='ws-1', baseline_id='base-new', baseline_version=11, baseline_digest='dig-11', rollback_baseline_id='base-old', rollback_version=10, target_consumer='c1', receipt=None, now=NOW)
    data.update(kw)
    return BaselineAdoptionRequest(**data)

def test_requires_authorization():
    assert evaluate_baseline_adoption(req()).state == 'review-required'
    assert evaluate_baseline_adoption(req(), authorize=True).state == 'authorized'

def test_valid_receipt_requires_final_human_approval():
    r=req(receipt=receipt())
    assert evaluate_baseline_adoption(r, authorize=True).state == 'receipt-required'
    assert evaluate_baseline_adoption(r, authorize=True, human_approved=True).state == 'adopted'

def test_stale_receipt_is_not_adopted():
    d=evaluate_baseline_adoption(req(receipt=receipt(observed_at=NOW-timedelta(hours=1))), authorize=True, human_approved=True)
    assert d.state == 'receipt-required'

def test_lineage_mismatch_is_not_adopted():
    d=evaluate_baseline_adoption(req(receipt=receipt(baseline_version=10)), authorize=True, human_approved=True)
    assert d.state == 'receipt-required'

def test_unhealthy_or_low_confidence_is_not_adopted():
    assert evaluate_baseline_adoption(req(receipt=receipt(healthy=False)), authorize=True, human_approved=True).state == 'receipt-required'
    assert evaluate_baseline_adoption(req(receipt=receipt(confidence=0.2)), authorize=True, human_approved=True).state == 'receipt-required'

def test_invalid_source_blocks():
    assert evaluate_baseline_adoption(req(source_state='committed'), authorize=True).state == 'blocked'

def test_duplicate_source_consumer_blocks_after_adoption():
    r=req(receipt=receipt())
    assert evaluate_baseline_adoption(r, authorize=True, human_approved=True).state == 'adopted'
    assert evaluate_baseline_adoption(r, authorize=True, human_approved=True).state == 'blocked'

def test_replayed_nonce_blocks():
    first=req(receipt=receipt(), source_id='s1')
    second=req(receipt=receipt(), source_id='s2')
    assert evaluate_baseline_adoption(first, authorize=True, human_approved=True).state == 'adopted'
    assert evaluate_baseline_adoption(second, authorize=True, human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_baseline_adoption(req(risk_brain_hard_block=True), authorize=True).state == 'blocked'
