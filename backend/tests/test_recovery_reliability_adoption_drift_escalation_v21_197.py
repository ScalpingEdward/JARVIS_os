import pytest
from app.schemas.recovery_reliability_adoption_drift_escalation_v21_197 import AdoptionDriftEscalationRequest, DriftedConsumer
from app.services.recovery_reliability_adoption_drift_escalation_v21_197 import evaluate_reconciliation_readiness, reset_seen_sources_for_tests

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_sources_for_tests()

def make_req(**kw):
    data = dict(source_id='obs-196-a', source_state='drift-detected', source_human_approved=True, workspace_id='ws-1', baseline_id='base-a', baseline_version=7, baseline_digest='digest-a', affected_consumers=[DriftedConsumer(consumer_id='c1', drift_reason='baseline-mismatch', severity='low', confidence=0.9)], healthy_consumers=['c2','c3'], max_blast_radius=0.5, max_residual_risk=0.35)
    data.update(kw)
    return AdoptionDriftEscalationRequest(**data)

def test_requires_human_approval_before_ready():
    d = evaluate_reconciliation_readiness(make_req())
    assert d.state == 'review-required'
    d2 = evaluate_reconciliation_readiness(make_req(), human_approved=True)
    assert d2.state == 'reconciliation-ready'

def test_invalid_source_is_blocked():
    assert evaluate_reconciliation_readiness(make_req(source_state='consistent')).state == 'blocked'

def test_overlap_is_blocked():
    assert evaluate_reconciliation_readiness(make_req(healthy_consumers=['c1','c2'])).state == 'blocked'

def test_blast_radius_limit_requires_review():
    d = evaluate_reconciliation_readiness(make_req(healthy_consumers=[]))
    assert d.state == 'review-required'
    assert 'blast-radius-limit-exceeded' in d.reasons

def test_critical_drift_requires_review():
    affected=[DriftedConsumer(consumer_id='c1', drift_reason='unhealthy', severity='critical', confidence=1.0)]
    d = evaluate_reconciliation_readiness(make_req(affected_consumers=affected))
    assert d.state == 'review-required'
    assert 'residual-risk-limit-exceeded' in d.reasons

def test_duplicate_source_blocks_after_approval():
    assert evaluate_reconciliation_readiness(make_req(), human_approved=True).state == 'reconciliation-ready'
    assert evaluate_reconciliation_readiness(make_req(), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_reconciliation_readiness(make_req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'
