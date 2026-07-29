from datetime import datetime, timedelta, timezone
import pytest
from app.schemas.recovery_reliability_recovery_receipt_v21_199 import RecoveryReceipt, RecoveryReceiptReconciliationRequest
from app.services.recovery_reliability_recovery_receipt_v21_199 import reconcile_recovery_receipts, reset_seen_sources_for_tests

NOW = datetime(2026, 7, 29, 18, 0, tzinfo=timezone.utc)

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_sources_for_tests()

def receipt(cid, **kw):
    data=dict(consumer_id=cid, workspace_id='ws-1', baseline_id='base-a', baseline_version=8, baseline_digest='dig-8', nonce='n-'+cid, observed_at=NOW-timedelta(seconds=30), recovered=True, healthy=True, recovery_quality=0.95)
    data.update(kw)
    return RecoveryReceipt(**data)

def req(**kw):
    data=dict(source_id='recovery-198-a', source_state='recovery-ready', source_human_approved=True, workspace_id='ws-1', baseline_id='base-a', baseline_version=8, baseline_digest='dig-8', expected_consumers=['c1','c2'], receipts=[receipt('c1'),receipt('c2')], now=NOW)
    data.update(kw)
    return RecoveryReceiptReconciliationRequest(**data)

def test_requires_human_approval_for_completion():
    assert reconcile_recovery_receipts(req()).state == 'review-required'
    assert reconcile_recovery_receipts(req(), human_approved=True).state == 'completed'

def test_missing_receipt_is_incomplete():
    d=reconcile_recovery_receipts(req(receipts=[receipt('c1')]))
    assert d.state == 'incomplete' and d.incomplete_consumers == ['c2']

def test_unhealthy_or_low_quality_is_incomplete():
    d=reconcile_recovery_receipts(req(receipts=[receipt('c1'),receipt('c2', healthy=False, recovery_quality=0.2)]))
    assert d.state == 'incomplete'

def test_stale_receipt_is_incomplete():
    d=reconcile_recovery_receipts(req(receipts=[receipt('c1'),receipt('c2', observed_at=NOW-timedelta(hours=1))]))
    assert d.state == 'incomplete'

def test_lineage_mismatch_is_incomplete():
    d=reconcile_recovery_receipts(req(receipts=[receipt('c1'),receipt('c2', baseline_version=7)]))
    assert d.state == 'incomplete'

def test_duplicate_nonce_blocks():
    d=reconcile_recovery_receipts(req(receipts=[receipt('c1', nonce='same'),receipt('c2', nonce='same')]))
    assert d.state == 'blocked'

def test_unexpected_consumer_blocks():
    d=reconcile_recovery_receipts(req(receipts=[receipt('c1'),receipt('c2'),receipt('c3')]))
    assert d.state == 'blocked'

def test_duplicate_source_blocks_after_completion():
    assert reconcile_recovery_receipts(req(), human_approved=True).state == 'completed'
    assert reconcile_recovery_receipts(req(), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert reconcile_recovery_receipts(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'
