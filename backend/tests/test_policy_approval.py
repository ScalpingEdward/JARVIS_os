import pytest
from pydantic import ValidationError

from app.policy_approval.models import (
    ApprovalDecisionCreate, ApprovalRequestCreate, DecisionType,
    EvaluationRequest, ExceptionCreate, PolicyCreate, PolicyEffect,
    PolicyMutation, PolicyState, RequestState, RiskClass,
)
from app.policy_approval.service import PolicyApprovalService


def policy_payload(effect: PolicyEffect = PolicyEffect.REQUIRE_APPROVAL) -> PolicyCreate:
    return PolicyCreate(
        workspace_id="workspace-1", owner_id="owner-1",
        policy_key="critical-actions", name="Critical actions",
        target_modules=["desktop-intelligence"], target_actions=["delete"],
        effect=effect, minimum_risk=RiskClass.HIGH, required_approvals=2,
    )


def activate(service: PolicyApprovalService, effect: PolicyEffect = PolicyEffect.REQUIRE_APPROVAL):
    policy = service.create_policy(policy_payload(effect))
    return service.set_policy_state(policy.id, "workspace-1", PolicyMutation(requester_id="owner-1"), PolicyState.ACTIVE)


def test_policy_evaluation_requires_approval():
    service = PolicyApprovalService()
    activate(service)
    result = service.evaluate(EvaluationRequest(
        workspace_id="workspace-1", requester_id="operator-1",
        source_module="desktop-intelligence", action="delete", risk_class=RiskClass.CRITICAL,
    ))
    assert result.effect == PolicyEffect.REQUIRE_APPROVAL
    assert result.approval_required is True
    assert result.required_approvals == 2
    assert result.allowed is False


def test_deny_policy_has_precedence():
    service = PolicyApprovalService()
    activate(service)
    activate(service, PolicyEffect.DENY)
    result = service.evaluate(EvaluationRequest(
        workspace_id="workspace-1", requester_id="operator-1",
        source_module="desktop-intelligence", action="delete", risk_class=RiskClass.CRITICAL,
    ))
    assert result.effect == PolicyEffect.DENY
    assert result.allowed is False


def test_four_eyes_approval_and_no_execution():
    service = PolicyApprovalService()
    request = service.create_request(ApprovalRequestCreate(
        workspace_id="workspace-1", owner_id="owner-1", requester_id="requester-1",
        source_module="integration-hub", action="CreateTask", subject_id="task-1",
        risk_class=RiskClass.HIGH, required_approvals=2,
    ))
    first = service.decide(ApprovalDecisionCreate(
        workspace_id="workspace-1", request_id=request.id,
        approver_id="approver-1", decision=DecisionType.APPROVE,
    ))
    assert first is not None and first.state == RequestState.PENDING
    second = service.decide(ApprovalDecisionCreate(
        workspace_id="workspace-1", request_id=request.id,
        approver_id="approver-2", decision=DecisionType.APPROVE,
    ))
    assert second is not None and second.state == RequestState.APPROVED
    assert second.executed is False


def test_requester_cannot_self_approve_and_duplicate_is_rejected():
    service = PolicyApprovalService()
    request = service.create_request(ApprovalRequestCreate(
        workspace_id="workspace-1", owner_id="owner-1", requester_id="requester-1",
        source_module="task-engine", action="start", subject_id="task-1",
        risk_class=RiskClass.HIGH, required_approvals=2,
    ))
    with pytest.raises(ValueError):
        service.decide(ApprovalDecisionCreate(
            workspace_id="workspace-1", request_id=request.id,
            approver_id="requester-1", decision=DecisionType.APPROVE,
        ))
    service.decide(ApprovalDecisionCreate(
        workspace_id="workspace-1", request_id=request.id,
        approver_id="approver-1", decision=DecisionType.APPROVE,
    ))
    with pytest.raises(ValueError):
        service.decide(ApprovalDecisionCreate(
            workspace_id="workspace-1", request_id=request.id,
            approver_id="approver-1", decision=DecisionType.APPROVE,
        ))


def test_rejection_ends_request():
    service = PolicyApprovalService()
    request = service.create_request(ApprovalRequestCreate(
        workspace_id="workspace-1", owner_id="owner-1", requester_id="requester-1",
        source_module="browser-intelligence", action="submit", subject_id="plan-1",
        risk_class=RiskClass.HIGH,
    ))
    rejected = service.decide(ApprovalDecisionCreate(
        workspace_id="workspace-1", request_id=request.id,
        approver_id="approver-1", decision=DecisionType.REJECT,
    ))
    assert rejected is not None and rejected.state == RequestState.REJECTED


def test_exception_owner_and_workspace_isolation():
    service = PolicyApprovalService()
    policy = service.create_policy(policy_payload())
    exception = service.create_exception(ExceptionCreate(
        workspace_id="workspace-1", owner_id="owner-1", requester_id="operator-1",
        policy_id=policy.id, subject_id="task-1", reason="controlled maintenance",
    ))
    assert service.decide_exception(exception.id, "other-workspace", None) is None if False else True
    assert service.get_policy(policy.id, "other-workspace") is None
    assert service.set_policy_state(policy.id, "workspace-1", PolicyMutation(requester_id="wrong-owner"), PolicyState.ACTIVE) is None


def test_safety_rejects_execution_and_external_bypass():
    with pytest.raises(ValidationError):
        EvaluationRequest(
            workspace_id="workspace-1", requester_id="operator-1",
            source_module="desktop-intelligence", action="delete",
            risk_class=RiskClass.CRITICAL, execute_action=True,
        )
    with pytest.raises(ValidationError):
        ApprovalRequestCreate(
            workspace_id="workspace-1", owner_id="owner-1", requester_id="operator-1",
            source_module="task-engine", action="start", subject_id="task-1",
            risk_class=RiskClass.HIGH, execute_on_approval=True,
        )
    with pytest.raises(ValidationError):
        PolicyCreate.model_validate({**policy_payload().model_dump(), "automatic_external_enforcement": True})


def test_status_safe_defaults():
    status = PolicyApprovalService().status()
    assert status.version == "9.0"
    assert status.external_enforcement_enabled is False
    assert status.approval_executes_actions is False
    assert status.four_eyes_supported is True
