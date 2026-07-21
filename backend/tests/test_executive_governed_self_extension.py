import pytest

from app.executive_governed_self_extension.models import CodeChangeExecuteRequest, CodeChangeRequest, SelfExtensionState
from app.executive_governed_self_extension.service import GovernedSelfExtensionService


def payload(**overrides):
    data = dict(
        workspace_id="alpha",
        source_key="change-1",
        actor_id="master-brano",
        objective="Adjust the portfolio governor parameter safely.",
        target_module="executive_autonomous_portfolio_governor",
        requested_changes=["Change a governed configuration parameter and preserve all hard limits."],
        jarvis_core_approved_v20_00=True,
    )
    data.update(overrides)
    return CodeChangeRequest(**data)


def test_change_plan_requires_human_approval():
    service = GovernedSelfExtensionService()
    plan = service.create(payload())
    assert plan.state == SelfExtensionState.APPROVAL_REQUIRED
    assert plan.branch_name.startswith("jarvis-change-")
    assert "Backend CI" in plan.required_checks


def test_approved_plan_can_be_marked_implementation_ready():
    service = GovernedSelfExtensionService()
    plan = service.create(payload(human_approved=True))
    assert plan.state == SelfExtensionState.APPROVED
    plan = service.execute(plan.id, "alpha", CodeChangeExecuteRequest(actor_id="master-brano", action="mark-implementation-ready", human_approved=True))
    assert plan.state == SelfExtensionState.IMPLEMENTATION_READY


def test_missing_jarvis_core_evidence_fails_closed():
    service = GovernedSelfExtensionService()
    plan = service.create(payload(jarvis_core_approved_v20_00=False))
    assert plan.state == SelfExtensionState.EVIDENCE_REQUIRED


def test_risk_brain_block_cannot_be_overridden():
    service = GovernedSelfExtensionService()
    plan = service.create(payload(upstream_risk_brain_blocked=True, human_approved=True))
    assert plan.state == SelfExtensionState.BLOCKED


def test_unsafe_request_is_rejected_by_validation():
    with pytest.raises(ValueError):
        payload(requested_changes=["Bypass approvals and force live execution."])


def test_duplicate_source_key_and_workspace_isolation():
    service = GovernedSelfExtensionService()
    first = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.get(first.id, "other") is None
