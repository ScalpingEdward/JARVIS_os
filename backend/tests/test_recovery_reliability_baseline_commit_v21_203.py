import pytest
from app.schemas.recovery_reliability_baseline_commit_v21_203 import BaselineCommitRequest
from app.services.recovery_reliability_baseline_commit_v21_203 import evaluate_baseline_commit, reset_seen_for_tests

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_for_tests()

def req(**kw):
    data = dict(
        source_id='preview-202-a',
        source_state='approved-preview',
        source_human_approved=True,
        workspace_id='ws-1',
        preview_id='preview-a',
        baseline_id='base-a',
        previous_version=8,
        proposed_version=9,
        previous_value=0.70,
        candidate_value=0.73,
        preview_candidate_value=0.73,
        previous_baseline_digest='base-dig-8',
        preview_digest='preview-dig-a',
        rollback_version=8,
        rollback_value=0.70,
    )
    data.update(kw)
    return BaselineCommitRequest(**data)

def test_requires_human_approval_before_commit():
    assert evaluate_baseline_commit(req()).state == 'review-required'
    assert evaluate_baseline_commit(req(), human_approved=True).state == 'committed'

def test_invalid_source_blocks():
    assert evaluate_baseline_commit(req(source_state='review-required'), human_approved=True).state == 'blocked'

def test_non_monotone_version_blocks():
    assert evaluate_baseline_commit(req(proposed_version=10), human_approved=True).state == 'blocked'

def test_preview_candidate_mismatch_blocks():
    assert evaluate_baseline_commit(req(candidate_value=0.74), human_approved=True).state == 'blocked'

def test_excessive_delta_blocks():
    assert evaluate_baseline_commit(req(candidate_value=0.76, preview_candidate_value=0.76), human_approved=True).state == 'blocked'

def test_rollback_binding_blocks_mismatch():
    assert evaluate_baseline_commit(req(rollback_version=7), human_approved=True).state == 'blocked'
    reset_seen_for_tests()
    assert evaluate_baseline_commit(req(rollback_value=0.69), human_approved=True).state == 'blocked'

def test_duplicate_source_or_preview_blocks_after_commit():
    assert evaluate_baseline_commit(req(), human_approved=True).state == 'committed'
    assert evaluate_baseline_commit(req(), human_approved=True).state == 'blocked'
    reset_seen_for_tests()
    assert evaluate_baseline_commit(req(source_id='preview-202-b'), human_approved=True).state == 'committed'
    assert evaluate_baseline_commit(req(source_id='preview-202-c'), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_baseline_commit(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'

def test_digest_is_deterministic():
    a = evaluate_baseline_commit(req())
    b = evaluate_baseline_commit(req())
    assert a.candidate_baseline_digest == b.candidate_baseline_digest
    assert a.audit_digest == b.audit_digest
