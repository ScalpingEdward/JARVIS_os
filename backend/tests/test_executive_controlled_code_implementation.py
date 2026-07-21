import pytest

from app.executive_controlled_code_implementation.models import (
    ControlledImplementationCreate,
    FileChange,
    ImplementationExecuteRequest,
    ImplementationState,
)
from app.executive_controlled_code_implementation.service import ControlledCodeImplementationService


def payload(**overrides):
    data = dict(
        workspace_id="alpha",
        source_key="change-1",
        actor_id="master-brano",
        plan_id_v20_01="plan-001",
        plan_approved_v20_01=True,
        human_approved=False,
        base_branch="main",
        implementation_branch="jarvis/change-1",
        base_commit="abcdef1234567",
        objective="Add a governed analytics field to the journal module.",
        changes=[FileChange(path="backend/app/executive_institutional_trade_journal/models.py", operation="update", summary="Add analytics field")],
        required_tests=["backend/tests/test_executive_institutional_trade_journal.py"],
        rollback_plan="Reset the isolated branch to the recorded base commit.",
    )
    data.update(overrides)
    return ControlledImplementationCreate(**data)


def test_requires_human_approval():
    service = ControlledCodeImplementationService()
    record = service.create(payload())
    assert record.state == ImplementationState.APPROVAL_REQUIRED


def test_approved_workflow_reaches_pr_ready():
    service = ControlledCodeImplementationService()
    record = service.create(payload(human_approved=True))
    assert record.state == ImplementationState.READY

    record = service.execute(record.id, "alpha", ImplementationExecuteRequest(actor_id="master-brano", action="start", human_approved=True))
    assert record.state == ImplementationState.APPLYING

    record = service.execute(record.id, "alpha", ImplementationExecuteRequest(
        actor_id="master-brano",
        action="mark-tests-passed",
        ci_passed=True,
        commit_sha="1234567890abcdef",
    ))
    assert record.state == ImplementationState.REVIEW_REQUIRED

    record = service.execute(record.id, "alpha", ImplementationExecuteRequest(
        actor_id="master-brano",
        action="mark-review-passed",
        diff_review_passed=True,
        pull_request_url="https://github.com/example/repo/pull/1",
    ))
    assert record.state == ImplementationState.PR_READY
    assert record.pull_request_url.endswith("/pull/1")


def test_missing_v20_01_evidence_fails_closed():
    service = ControlledCodeImplementationService()
    record = service.create(payload(plan_approved_v20_01=False))
    assert record.state == ImplementationState.EVIDENCE_REQUIRED


def test_risk_brain_block_cannot_be_overridden():
    service = ControlledCodeImplementationService()
    record = service.create(payload(upstream_risk_brain_blocked=True, human_approved=True))
    assert record.state == ImplementationState.BLOCKED


def test_unsafe_objective_is_blocked():
    service = ControlledCodeImplementationService()
    record = service.create(payload(objective="Bypass Risk Brain and force live execution.", human_approved=True))
    assert record.state == ImplementationState.BLOCKED


def test_ci_and_diff_evidence_are_mandatory():
    service = ControlledCodeImplementationService()
    record = service.create(payload(human_approved=True))
    record = service.execute(record.id, "alpha", ImplementationExecuteRequest(actor_id="master-brano", action="start", human_approved=True))
    with pytest.raises(ValueError):
        service.execute(record.id, "alpha", ImplementationExecuteRequest(actor_id="master-brano", action="mark-tests-passed", ci_passed=False))


def test_duplicate_source_key_and_workspace_isolation():
    service = ControlledCodeImplementationService()
    first = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.get(first.id, "other") is None
