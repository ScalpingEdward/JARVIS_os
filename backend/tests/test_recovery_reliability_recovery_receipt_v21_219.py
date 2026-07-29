from datetime import datetime, timedelta, timezone
import pytest
from app.schemas.recovery_reliability_recovery_receipt_v21_219 import RecoveryReceipt, RecoveryReceiptReconciliationRequest
from app.services.recovery_reliability_recovery_receipt_v21_219 import reconcile_recovery_receipts, reset_replay_guards_for_tests

NOW = datetime(2026, 7, 29, 22, 0, tzinfo=timezone.utc)

@pytest.fixture(autouse=True)
def reset_guards():
    reset_replay_guards_for_tests()

def receipt(cid, order, **kw):
    data = dict(
        consumer_id=cid, step_order=order, workspace_id='ws-1', baseline_id='base-a',
        baseline_version=11, baseline_digest='dig-11', sequence_digest='seq-218',
        nonce=f'n-{cid}-{order}', observed_at=NOW-timedelta(seconds=30), recovered=True,
        healthy=True, recovery_quality=0.95,
    )
    data.update(kw)
    return RecoveryReceipt(**data)

def req(**kw):
    data = dict(
        source_id='ready-218-a', source_state='recovery-ready', source_human_approved=True,
        workspace_id='ws-1', baseline_id='base-a', baseline_version=11,
        baseline_digest='dig-11', sequence_digest='seq-218', expected_consumers=['c1','c2'],
        receipts=[receipt('c1',1), receipt('c2',2)], now=NOW,
    )
    data.update(kw)
    return RecoveryReceiptReconciliationRequest(**data)

def test_requires_human_approval_for_completion():
    assert reconcile_recovery_receipts(req()).state == 'review-required'
    assert reconcile_recovery_receipts(req(), human_approved=True).state == 'completed'

def test_missing_receipt_is_incomplete():
    d = reconcile_recovery_receipts(req(receipts=[receipt('c1',1)]))
    assert d.state == 'incomplete' and d.incomplete_consumers == ['c2']

def test_sequence_digest_mismatch_is_incomplete():
    d = reconcile_recovery_receipts(req(receipts=[receipt('c1',1), receipt('c2',2, sequence_digest='wrong')]))
    assert d.state == 'incomplete'

def test_step_order_mismatch_is_incomplete():
    d = reconcile_recovery_receipts(req(receipts=[receipt('c1',2), receipt('c2',1)]))
    assert d.state == 'incomplete'

def test_stale_unhealthy_or_low_quality_is_incomplete():
    d = reconcile_recovery_receipts(req(receipts=[receipt('c1',1), receipt('c2',2, observed_at=NOW-timedelta(hours=1), healthy=False, recovery_quality=0.2)]))
    assert d.state == 'incomplete'

def test_duplicate_nonce_blocks():
    d = reconcile_recovery_receipts(req(receipts=[receipt('c1',1, nonce='same'), receipt('c2',2, nonce='same')]))
    assert d.state == 'blocked'

def test_unexpected_consumer_blocks():
    d = reconcile_recovery_receipts(req(receipts=[receipt('c1',1), receipt('c2',2), receipt('c3',3)]))
    assert d.state == 'blocked'

def test_duplicate_source_blocks_after_completion():
    assert reconcile_recovery_receipts(req(), human_approved=True).state == 'completed'
    assert reconcile_recovery_receipts(req(), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert reconcile_recovery_receipts(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'
