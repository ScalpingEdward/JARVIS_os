import pytest
from app.schemas.recovery_reliability_adoption_drift_escalation_v21_217 import AdoptionDriftEscalationRequest, DriftedConsumer
from app.services.recovery_reliability_adoption_drift_escalation_v21_217 import evaluate_reconciliation_readiness, reset_seen_sources_for_tests

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_sources_for_tests()

def drift(cid='c1', severity='low', confidence=0.9):
    return DriftedConsumer(consumer_id=cid, drift_reason='baseline-mismatch', severity=severity, confidence=confidence)

def req(**kw):
    data=dict(source_id='drift-216-a', source_state='drift-detected', source_human_approved=True, workspace_id='ws-1', baseline_id='base-a', baseline_version=11, baseline_digest='dig-11', affected_consumers=[drift()], healthy_consumers=['c2','c3'], max_blast_radius=0.5, max_residual_risk=0.35)
    data.update(kw)
    return AdoptionDriftEscalationRequest(**data)

def test_requires_human_approval_before_ready():
    assert evaluate_reconciliation_readiness(req()).state == 'review-required'
    assert evaluate_reconciliation_readiness(req(), human_approved=True).state == 'reconciliation-ready'

def test_invalid_source_blocks():
    assert evaluate_reconciliation_readiness(req(source_state='consistent')).state == 'blocked'

def test_duplicate_affected_consumer_blocks():
    assert evaluate_reconciliation_readiness(req(affected_consumers=[drift('c1'), drift('c1')])).state == 'blocked'

def test_overlap_blocks():
    assert evaluate_reconciliation_readiness(req(healthy_consumers=['c1','c2'])).state == 'blocked'

def test_blast_radius_limit_requires_review():
    d=evaluate_reconciliation_readiness(req(healthy_consumers=[]), human_approved=True)
    assert d.state == 'review-required'
    assert 'blast-radius-limit-exceeded' in d.reasons

def test_critical_drift_requires_review():
    d=evaluate_reconciliation_readiness(req(affected_consumers=[drift(severity='critical', confidence=1.0)]), human_approved=True)
    assert d.state == 'review-required'
    assert 'residual-risk-limit-exceeded' in d.reasons

def test_duplicate_source_blocks_after_ready():
    assert evaluate_reconciliation_readiness(req(), human_approved=True).state == 'reconciliation-ready'
    assert evaluate_reconciliation_readiness(req(), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_reconciliation_readiness(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'
