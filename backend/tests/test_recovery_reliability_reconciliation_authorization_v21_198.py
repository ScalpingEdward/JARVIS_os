import pytest
from app.schemas.recovery_reliability_reconciliation_authorization_v21_198 import ReconciliationAuthorizationRequest, RecoveryStep
from app.services.recovery_reliability_reconciliation_authorization_v21_198 import authorize_reconciliation, reset_seen_sources_for_tests

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_sources_for_tests()

def make_req(**kw):
    data = dict(
        source_id='ready-197-a', source_state='reconciliation-ready', source_human_approved=True,
        workspace_id='ws-1', baseline_id='base-a', baseline_version=7, baseline_digest='digest-a',
        affected_consumers=['c1','c2'], healthy_consumers=['c3'],
        recovery_steps=[RecoveryStep(order=1, consumer_id='c1', drift_reason='baseline-mismatch'), RecoveryStep(order=2, consumer_id='c2', drift_reason='unhealthy')],
        blast_radius=0.4, residual_risk=0.2,
    )
    data.update(kw)
    return ReconciliationAuthorizationRequest(**data)

def test_human_authorization_required():
    assert authorize_reconciliation(make_req()).state == 'review-required'
    assert authorize_reconciliation(make_req(), actor='human', human_authorized=True).state == 'authorized'

def test_partial_ordered_step_approval_is_staged():
    steps=[RecoveryStep(order=1, consumer_id='c1', drift_reason='baseline-mismatch', approved=True), RecoveryStep(order=2, consumer_id='c2', drift_reason='unhealthy')]
    d = authorize_reconciliation(make_req(recovery_steps=steps), actor='human', human_authorized=True)
    assert d.state == 'staged'

def test_all_steps_approved_becomes_recovery_ready():
    steps=[RecoveryStep(order=1, consumer_id='c1', drift_reason='baseline-mismatch', approved=True), RecoveryStep(order=2, consumer_id='c2', drift_reason='unhealthy', approved=True)]
    d = authorize_reconciliation(make_req(recovery_steps=steps), actor='human', human_authorized=True)
    assert d.state == 'recovery-ready'

def test_out_of_order_step_approval_blocks():
    steps=[RecoveryStep(order=1, consumer_id='c1', drift_reason='baseline-mismatch'), RecoveryStep(order=2, consumer_id='c2', drift_reason='unhealthy', approved=True)]
    d = authorize_reconciliation(make_req(recovery_steps=steps), actor='human', human_authorized=True)
    assert d.state == 'blocked'
    assert 'out-of-order-step-approval' in d.reasons

def test_healthy_consumer_preservation_overlap_blocks():
    assert authorize_reconciliation(make_req(healthy_consumers=['c2','c3'])).state == 'blocked'

def test_sequence_coverage_mismatch_blocks():
    steps=[RecoveryStep(order=1, consumer_id='c1', drift_reason='baseline-mismatch')]
    assert authorize_reconciliation(make_req(recovery_steps=steps)).state == 'blocked'

def test_limits_require_review():
    assert authorize_reconciliation(make_req(blast_radius=0.8), actor='human', human_authorized=True).state == 'review-required'
    assert authorize_reconciliation(make_req(residual_risk=0.8), actor='human', human_authorized=True).state == 'review-required'

def test_invalid_source_and_risk_brain_fail_closed():
    assert authorize_reconciliation(make_req(source_state='drift-detected')).state == 'blocked'
    assert authorize_reconciliation(make_req(risk_brain_hard_block=True), actor='human', human_authorized=True).state == 'blocked'

def test_duplicate_source_blocks_after_recovery_ready():
    steps=[RecoveryStep(order=1, consumer_id='c1', drift_reason='baseline-mismatch', approved=True), RecoveryStep(order=2, consumer_id='c2', drift_reason='unhealthy', approved=True)]
    req = make_req(recovery_steps=steps)
    assert authorize_reconciliation(req, actor='human', human_authorized=True).state == 'recovery-ready'
    assert authorize_reconciliation(req, actor='human', human_authorized=True).state == 'blocked'
