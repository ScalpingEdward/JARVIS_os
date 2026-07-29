import pytest
from app.schemas.recovery_reliability_baseline_rollout_v21_214 import BaselineRolloutRequest, RolloutStage
from app.services.recovery_reliability_baseline_rollout_v21_214 import evaluate_rollout, reset_seen_sources_for_tests

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_sources_for_tests()

def stage(order, consumers, approved=False, max_exposure=0.5):
    return RolloutStage(order=order, consumer_ids=consumers, approved=approved, max_exposure=max_exposure)

def req(**kw):
    data=dict(source_id='commit-213-a', source_state='committed', source_human_approved=True, workspace_id='ws-1', baseline_id='base-11', baseline_version=11, baseline_digest='dig-11', rollback_baseline_id='base-10', rollback_version=10, candidate_consumers=['c1','c2','c3','c4'], stages=[stage(1,['c1','c2']), stage(2,['c3','c4'])])
    data.update(kw)
    return BaselineRolloutRequest(**data)

def test_requires_human_approval_for_eligibility():
    assert evaluate_rollout(req()).state == 'review-required'
    assert evaluate_rollout(req(), human_approved=True).state == 'eligible'

def test_all_stage_approvals_produce_staged():
    d=evaluate_rollout(req(stages=[stage(1,['c1','c2'],True),stage(2,['c3','c4'],True)]), human_approved=True)
    assert d.state == 'staged'

def test_incomplete_coverage_blocks():
    assert evaluate_rollout(req(stages=[stage(1,['c1','c2'])]), human_approved=True).state == 'blocked'

def test_overlap_blocks():
    assert evaluate_rollout(req(stages=[stage(1,['c1','c2']),stage(2,['c2','c3','c4'],max_exposure=0.75)]), human_approved=True).state == 'blocked'

def test_exposure_limit_holds_for_review():
    d=evaluate_rollout(req(stages=[stage(1,['c1','c2','c3'],max_exposure=0.5),stage(2,['c4'])]), human_approved=True)
    assert d.state == 'review-required'

def test_out_of_order_stage_approval_blocks():
    d=evaluate_rollout(req(stages=[stage(1,['c1','c2']),stage(2,['c3','c4'],True)]), human_approved=True)
    assert d.state == 'blocked'

def test_duplicate_source_blocks_after_staged():
    staged=req(stages=[stage(1,['c1','c2'],True),stage(2,['c3','c4'],True)])
    assert evaluate_rollout(staged, human_approved=True).state == 'staged'
    assert evaluate_rollout(staged, human_approved=True).state == 'blocked'

def test_invalid_source_blocks():
    assert evaluate_rollout(req(source_state='approved-preview'), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_rollout(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'
