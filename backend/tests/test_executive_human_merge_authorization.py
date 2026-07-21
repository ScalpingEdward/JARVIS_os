from app.executive_human_merge_authorization.models import (
    MergeAuthorizationCreate,
    MergeAuthorizationExecuteRequest,
    MergeAuthorizationState,
    MergeEvidence,
)
from app.executive_human_merge_authorization.service import HumanMergeAuthorizationService


def payload(**overrides):
    data = dict(
        workspace_id="alpha",
        source_key="merge-249",
        actor_id="master-brano",
        release_notes="Release candidate for governed merge authorization.",
        evidence=MergeEvidence(
            pull_request_number=249,
            branch_name="feature/governed-change",
            head_commit_sha="abcdef1234567890",
            base_commit_sha="1234567890abcdef",
            ci_passed=True,
            tests_passed=True,
            diff_reviewed=True,
            rollback_verified=True,
            v20_03_merge_recommended=True,
        ),
    )
    data.update(overrides)
    return MergeAuthorizationCreate(**data)


def test_clean_change_waits_for_human_authorization():
    service = HumanMergeAuthorizationService()
    record = service.create(payload())
    assert record.state == MergeAuthorizationState.AUTHORIZATION_PENDING


def test_release_candidate_can_receive_explicit_merge_authorization():
    service = HumanMergeAuthorizationService()
    record = service.create(payload(human_approved=True))
    assert record.state == MergeAuthorizationState.RELEASE_CANDIDATE
    record = service.execute(
        record.id,
        "alpha",
        MergeAuthorizationExecuteRequest(
            actor_id="master-brano",
            action="authorize-merge",
            human_approved=True,
            confirmation_token="MERGE-249-APPROVED",
        ),
    )
    assert record.state == MergeAuthorizationState.MERGE_AUTHORIZED
    assert record.merge_authorized is True


def test_sensitive_change_requires_separate_human_review():
    service = HumanMergeAuthorizationService()
    evidence = payload().evidence.model_copy(update={"risk_or_execution_changed": True})
    record = service.create(payload(evidence=evidence, human_approved=True))
    assert record.state == MergeAuthorizationState.HUMAN_REVIEW_REQUIRED


def test_failed_ci_and_missing_recommendation_fail_closed():
    service = HumanMergeAuthorizationService()
    failed = payload().evidence.model_copy(update={"ci_passed": False})
    assert service.create(payload(source_key="ci-fail", evidence=failed)).state == MergeAuthorizationState.BLOCKED
    missing = payload().evidence.model_copy(update={"v20_03_merge_recommended": False})
    assert service.create(payload(source_key="evidence-fail", evidence=missing)).state == MergeAuthorizationState.EVIDENCE_REQUIRED


def test_risk_brain_block_duplicate_and_workspace_isolation():
    service = HumanMergeAuthorizationService()
    blocked = service.create(payload(source_key="blocked", upstream_risk_brain_blocked=True))
    assert blocked.state == MergeAuthorizationState.BLOCKED
    first = service.create(payload())
    try:
        service.create(payload())
        assert False, "expected duplicate rejection"
    except ValueError:
        pass
    assert service.get(first.id, "other") is None
