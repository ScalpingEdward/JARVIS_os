import pytest
from app.schemas.recovery_reliability_adoption_drift_escalation_v21_207 import DriftEscalationRequest, DriftConsumer
from app.services.recovery_reliability_adoption_drift_escalation_v21_207 import evaluate, reset_seen_sources_for_tests

@pytest.fixture(autouse=True)
def reset_seen(): reset_seen_sources_for_tests()

def make_req(**kw):
    data=dict(source_id='obs-206-a',source_state='drift-detected',source_human_approved=True,workspace_id='ws-1',baseline_id='base-a',baseline_version=9,baseline_digest='dig-9',affected_consumers=[DriftConsumer(consumer_id='c1',drift_reason='baseline-mismatch',severity='low',confidence=0.9)],healthy_consumers=['c2','c3'],max_blast_radius=0.5,max_residual_risk=0.35)
    data.update(kw); return DriftEscalationRequest(**data)

def test_human_approval_required():
    assert evaluate(make_req()).state=='review-required'
    assert evaluate(make_req(),human_approved=True).state=='reconciliation-ready'

def test_invalid_source_blocks(): assert evaluate(make_req(source_state='consistent')).state=='blocked'
def test_overlap_blocks(): assert evaluate(make_req(healthy_consumers=['c1'])).state=='blocked'
def test_blast_limit_requires_review(): assert evaluate(make_req(healthy_consumers=[])).state=='review-required'
def test_critical_risk_requires_review():
    d=evaluate(make_req(affected_consumers=[DriftConsumer(consumer_id='c1',drift_reason='unhealthy',severity='critical',confidence=1.0)]))
    assert d.state=='review-required' and 'residual-risk-limit-exceeded' in d.reasons

def test_duplicate_source_blocks_after_ready():
    assert evaluate(make_req(),human_approved=True).state=='reconciliation-ready'
    assert evaluate(make_req(),human_approved=True).state=='blocked'

def test_risk_brain_blocks(): assert evaluate(make_req(risk_brain_hard_block=True),human_approved=True).state=='blocked'
