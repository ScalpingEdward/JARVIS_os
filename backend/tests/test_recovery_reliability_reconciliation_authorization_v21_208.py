import pytest
from app.schemas.recovery_reliability_reconciliation_authorization_v21_208 import ReconciliationAuthorizationRequest, RecoveryStep
from app.services.recovery_reliability_reconciliation_authorization_v21_208 import evaluate_recovery_authorization, reset_seen_sources_for_tests

@pytest.fixture(autouse=True)
def reset_seen(): reset_seen_sources_for_tests()

def step(order, cid, approved=False):
    return RecoveryStep(order=order, consumer_id=cid, drift_reason='baseline-mismatch', action='reconcile', approved=approved)

def req(**kw):
    data=dict(source_id='ready-207-a', source_state='reconciliation-ready', source_human_approved=True, workspace_id='ws-1', baseline_id='base-a', baseline_version=9, baseline_digest='dig-9', affected_consumers=['c1','c2'], healthy_consumers=['c3'], recovery_steps=[step(1,'c1'),step(2,'c2')], blast_radius=0.4, residual_risk=0.2)
    data.update(kw); return ReconciliationAuthorizationRequest(**data)

def test_requires_authorization():
    assert evaluate_recovery_authorization(req()).state == 'review-required'
    assert evaluate_recovery_authorization(req(), authorize=True).state == 'authorized'

def test_partial_ordered_approval_is_staged():
    d=evaluate_recovery_authorization(req(recovery_steps=[step(1,'c1',True),step(2,'c2')]), authorize=True)
    assert d.state == 'staged'

def test_all_steps_approved_is_recovery_ready():
    d=evaluate_recovery_authorization(req(recovery_steps=[step(1,'c1',True),step(2,'c2',True)]), authorize=True)
    assert d.state == 'recovery-ready'

def test_out_of_order_approval_blocks():
    d=evaluate_recovery_authorization(req(recovery_steps=[step(1,'c1'),step(2,'c2',True)]), authorize=True)
    assert d.state == 'blocked'

def test_sequence_coverage_mismatch_blocks():
    assert evaluate_recovery_authorization(req(recovery_steps=[step(1,'c1')]), authorize=True).state == 'blocked'

def test_healthy_consumer_target_blocks():
    assert evaluate_recovery_authorization(req(recovery_steps=[step(1,'c1'),step(2,'c3')]), authorize=True).state == 'blocked'

def test_limits_hold_for_review():
    assert evaluate_recovery_authorization(req(blast_radius=0.9), authorize=True).state == 'review-required'

def test_duplicate_source_blocks_after_ready():
    ready=req(recovery_steps=[step(1,'c1',True),step(2,'c2',True)])
    assert evaluate_recovery_authorization(ready, authorize=True).state == 'recovery-ready'
    assert evaluate_recovery_authorization(ready, authorize=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_recovery_authorization(req(risk_brain_hard_block=True), authorize=True).state == 'blocked'
