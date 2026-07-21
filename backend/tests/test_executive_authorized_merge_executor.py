import pytest

from app.executive_authorized_merge_executor.models import (
    AuthorizedMergeCreate,
    MergeExecutionEvidence,
    MergeExecutionRequest,
    MergeExecutionState,
)
from app.executive_authorized_merge_executor.service import AuthorizedMergeExecutorService


def payload(**overrides):
    data = dict(
        workspace_id="alpha",
        source_key="merge-1",
        actor_id="master-brano",
        human_approved=True,
        evidence=MergeExecutionEvidence(
            pull_request_number=250,
            authorized_head_sha="abcdef1234567",
            current_head_sha="abcdef1234567",
            base_branch="main",
            authorization_token="AUTH-12345678",
            v20_04_merge_authorized=True,
            ci_passed=True,
            tests_passed=True,
            unresolved_comments=0,
            rollback_verified=True,
            mergeable=True,
        ),
    )
    data.update(overrides)
    return AuthorizedMergeCreate(**data)


def test_authorized_merge_reaches_ready_state():
    service = AuthorizedMergeExecutorService()
    record = service.create(payload())
    assert record.state == MergeExecutionState.READY


def test_full_merge_and_post_merge_verification_workflow():
    service = AuthorizedMergeExecutorService()
    record = service.create(payload())
    record = service.execute(record.id, "alpha", MergeExecutionRequest(actor_id="master-brano", action="request-merge", human_approved=True))
    assert record.state == MergeExecutionState.MERGE_REQUESTED
    record = service.execute(record.id, "alpha", MergeExecutionRequest(actor_id="master-brano", action="confirm-merged", merge_commit_sha="1234567890abc"))
    assert record.state == MergeExecutionState.POST_MERGE_VERIFYING
    record = service.execute(record.id, "alpha", MergeExecutionRequest(actor_id="master-brano", action="verify-post-merge", post_merge_ci_passed=True, post_merge_tests_passed=True))
    assert record.state == MergeExecutionState.VERIFIED


def test_failed_post_merge_verification_requires_rollback():
    service = AuthorizedMergeExecutorService()
    record = service.create(payload())
    record = service.execute(record.id, "alpha", MergeExecutionRequest(actor_id="master-brano", action="request-merge", human_approved=True))
    record = service.execute(record.id, "alpha", MergeExecutionRequest(actor_id="master-brano", action="confirm-merged", merge_commit_sha="1234567890abc"))
    record = service.execute(record.id, "alpha", MergeExecutionRequest(actor_id="master-brano", action="verify-post-merge", post_merge_ci_passed=False, post_merge_tests_passed=True))
    assert record.state == MergeExecutionState.ROLLBACK_REQUIRED


def test_missing_v20_04_authorization_fails_closed():
    service = AuthorizedMergeExecutorService()
    evidence = payload().evidence.model_copy(update={"v20_04_merge_authorized": False})
    record = service.create(payload(evidence=evidence))
    assert record.state == MergeExecutionState.EVIDENCE_REQUIRED


def test_risk_brain_block_and_workspace_isolation():
    service = AuthorizedMergeExecutorService()
    record = service.create(payload(upstream_risk_brain_blocked=True))
    assert record.state == MergeExecutionState.BLOCKED
    assert service.get(record.id, "other") is None


def test_duplicate_source_key_rejected():
    service = AuthorizedMergeExecutorService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
