import pytest
from app.schemas.recovery_reliability_baseline_rollout_v21_224 import BaselineRolloutRequest, RolloutStage
from app.services.recovery_reliability_baseline_rollout_v21_224 import evaluate_rollout, reset_seen_sources_for_tests

@pytest.fixture(autouse=True)
def reset_seen(): reset_seen_sources_for_tests()

def stage(order, consumers, exposure=0.4, approved=False):
    return RolloutStage(order=order, consumers=consumers, exposure=exposure, approved=approved)

def req(**kw):
    data=dict(source_id='commit-223-a', source_state='committed', source_human_approved=True, workspace_id='ws-1', candidate_baseline_id='base-b', candidate_version=12, candidate_digest='dig-b', rollback_baseline_id='base-a', rollback_version=11, rollback_digest='dig-a', recovery_sequence_digest='seq-1', candidate_consumers=['c1','c2'], stages=[stage(1,['c1']),stage(2,['c2'])])
    data.update(kw); return BaselineRolloutRequest(**data)

def test_requires_human_approval():
    assert evaluate_rollout(req()).state == 'review-required'

def test_approved_without_stage_approvals_is_eligible():
    assert evaluate_rollout(req(), human_approved=True).state == 'eligible'

def test_all_stages_approved_is_staged():
    d=evaluate_rollout(req(stages=[stage(1,['c1'],approved=True),stage(2,['c2'],approved=True)]), human_approved=True)
    assert d.state == 'staged'

def test_out_of_order_stage_approval_blocks():
    d=evaluate_rollout(req(stages=[stage(1,['c1']),stage(2,['c2'],approved=True)]), human_approved=True)
    assert d.state == 'blocked'

def test_coverage_mismatch_blocks():
    assert evaluate_rollout(req(stages=[stage(1,['c1'])]), human_approved=True).state == 'blocked'

def test_overlap_blocks():
    assert evaluate_rollout(req(stages=[stage(1,['c1']),stage(2,['c1'])]), human_approved=True).state == 'blocked'

def test_exposure_limit_holds_for_review():
    d=evaluate_rollout(req(stages=[stage(1,['c1'],0.8),stage(2,['c2'])]), human_approved=True)
    assert d.state == 'review-required'

def test_invalid_source_blocks():
    assert evaluate_rollout(req(source_state='approved-preview'), human_approved=True).state == 'blocked'

def test_duplicate_source_blocks_after_staged():
    r=req(stages=[stage(1,['c1'],approved=True),stage(2,['c2'],approved=True)])
    assert evaluate_rollout(r, human_approved=True).state == 'staged'
    assert evaluate_rollout(r, human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_rollout(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'
