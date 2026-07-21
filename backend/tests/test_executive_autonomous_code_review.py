from app.executive_autonomous_code_review.models import (
    AutonomousCodeReviewCreate,
    CodeReviewExecuteRequest,
    CodeReviewState,
    ReviewEvidence,
)
from app.executive_autonomous_code_review.service import AutonomousCodeReviewService


def evidence(**overrides):
    data = dict(
        implementation_id="impl-1",
        branch_name="feature-safe-change",
        base_commit="1234567",
        head_commit="89abcde",
        draft_pr_url="https://github.com/example/repo/pull/1",
        changed_files=["backend/app/module.py", "backend/tests/test_module.py"],
        additions=50,
        deletions=10,
        tests_added=3,
        tests_passed=100,
        tests_failed=0,
        coverage_pct=85,
        ci_passed=True,
        diff_reviewed=True,
        rollback_verified=True,
    )
    data.update(overrides)
    return ReviewEvidence(**data)


def payload(**overrides):
    data = dict(
        workspace_id="alpha",
        source_key="review-1",
        actor_id="master-brano",
        objective="Review the approved implementation.",
        v20_02_pr_ready=True,
        evidence=evidence(),
    )
    data.update(overrides)
    return AutonomousCodeReviewCreate(**data)


def test_clean_review_requires_confirmation_before_merge_recommendation():
    service = AutonomousCodeReviewService()
    record = service.create(payload())
    assert record.state == CodeReviewState.REVIEW_PENDING
    record = service.execute(
        record.id,
        "alpha",
        CodeReviewExecuteRequest(actor_id="master-brano", action="recommend-merge", human_approved=True),
    )
    assert record.state == CodeReviewState.MERGE_RECOMMENDED


def test_failed_ci_requires_changes():
    service = AutonomousCodeReviewService()
    record = service.create(payload(evidence=evidence(ci_passed=False)))
    assert record.state == CodeReviewState.CHANGES_REQUIRED
    assert record.recommendation == "reject"


def test_sensitive_changes_require_human_review():
    service = AutonomousCodeReviewService()
    record = service.create(payload(evidence=evidence(risk_or_execution_changed=True)))
    assert record.state == CodeReviewState.HUMAN_REVIEW_REQUIRED


def test_missing_v20_02_evidence_fails_closed():
    service = AutonomousCodeReviewService()
    record = service.create(payload(v20_02_pr_ready=False))
    assert record.state == CodeReviewState.EVIDENCE_REQUIRED


def test_risk_brain_block_cannot_be_overridden():
    service = AutonomousCodeReviewService()
    record = service.create(payload(upstream_risk_brain_blocked=True))
    assert record.state == CodeReviewState.BLOCKED


def test_duplicate_source_key_and_workspace_isolation():
    service = AutonomousCodeReviewService()
    first = service.create(payload())
    try:
        service.create(payload())
        assert False, "expected duplicate rejection"
    except ValueError:
        pass
    assert service.get(first.id, "other") is None
