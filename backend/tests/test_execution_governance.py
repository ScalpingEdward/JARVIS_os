import pytest

from app.execution_governance.models import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStage,
    ExecutionGateInput,
    GateType,
    ReleaseCreate,
    ReleaseStatus,
)
from app.execution_governance.service import ExecutionGovernanceService


def payload(workspace_id: str = "workspace-a") -> ReleaseCreate:
    return ReleaseCreate(
        workspace_id=workspace_id,
        owner_id="owner-1",
        title="Governed production release",
        target_type="mission",
        target_id="mission-42",
        emergency_stop_ready=True,
        rollback_steps=["Disable release", "Restore previous version"],
        dry_run_completed=True,
        checklist_items=["backup", "monitoring"],
        completed_checklist_items=["backup", "monitoring"],
        gates=[ExecutionGateInput(key="policy", gate_type=GateType.policy, title="Policy compliance", passed=True)],
        approval_stages=[ApprovalStage(key="operations", title="Operations approval", approver_roles=["operator"])],
    )


def test_ready_release_requires_human_approval_and_never_executes():
    service = ExecutionGovernanceService()
    record = service.create(payload())
    validated = service.validate(record.id, "workspace-a", "validator-1")

    assert validated.status == ReleaseStatus.pending_approval
    assert validated.validation is not None
    assert validated.validation.readiness_score == 100.0
    assert validated.validation.autonomous_execution_enabled is False
    assert validated.validation.requires_human_approval is True


def test_blocked_release_cannot_be_approved():
    service = ExecutionGovernanceService()
    request = payload()
    request.change_freeze_active = True
    record = service.create(request)
    validated = service.validate(record.id, "workspace-a", "validator-1")

    assert validated.status == ReleaseStatus.blocked
    with pytest.raises(ValueError, match="Blocked releases"):
        service.approve(record.id, ApprovalRequest(workspace_id="workspace-a", reviewer_id="reviewer-1", reviewer_role="operator", stage_key="operations", decision=ApprovalDecision.approve, reason="Approve release"))


def test_owner_cannot_self_approve_and_role_is_enforced():
    service = ExecutionGovernanceService()
    record = service.create(payload())
    service.validate(record.id, "workspace-a", "validator-1")

    with pytest.raises(ValueError, match="cannot approve"):
        service.approve(record.id, ApprovalRequest(workspace_id="workspace-a", reviewer_id="owner-1", reviewer_role="operator", stage_key="operations", decision=ApprovalDecision.approve, reason="Self approval"))
    with pytest.raises(ValueError, match="role"):
        service.approve(record.id, ApprovalRequest(workspace_id="workspace-a", reviewer_id="reviewer-1", reviewer_role="developer", stage_key="operations", decision=ApprovalDecision.approve, reason="Wrong role"))


def test_independent_reviewer_can_complete_release_approval():
    service = ExecutionGovernanceService()
    record = service.create(payload())
    service.validate(record.id, "workspace-a", "validator-1")
    approved = service.approve(record.id, ApprovalRequest(workspace_id="workspace-a", reviewer_id="reviewer-2", reviewer_role="operator", stage_key="operations", decision=ApprovalDecision.approve, reason="All gates reviewed"))

    assert approved.status == ReleaseStatus.approved
    assert approved.approvals[0].reviewer_id == "reviewer-2"


def test_workspace_isolation_and_duplicate_protection():
    service = ExecutionGovernanceService()
    record = service.create(payload())

    assert service.get(record.id, "workspace-b") is None
    assert service.list_records("workspace-b") == []
    with pytest.raises(ValueError, match="already exists"):
        service.create(payload())
