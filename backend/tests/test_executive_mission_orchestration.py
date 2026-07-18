import pytest

from app.executive_mission_orchestration.models import AgentCapacity, ApprovalDecision, ApprovalRequest, MissionInput, MissionTaskInput, OrchestrationCreate, OrchestrationStatus
from app.executive_mission_orchestration.service import ExecutiveMissionOrchestrationService


def payload(workspace_id: str = "workspace-a") -> OrchestrationCreate:
    return OrchestrationCreate(
        workspace_id=workspace_id,
        owner_id="owner-1",
        title="Executive launch portfolio",
        max_parallel_tasks=2,
        planning_horizon_hours=40,
        agents=[
            AgentCapacity(agent_id="agent-planner", capabilities=["planning", "analysis"], available_hours=24, reliability=0.95),
            AgentCapacity(agent_id="agent-builder", capabilities=["implementation", "testing"], available_hours=24, reliability=0.9),
        ],
        missions=[MissionInput(
            key="launch",
            title="Launch governed capability",
            objective="Plan, implement and validate a governed capability",
            priority="critical",
            strategic_value=95,
            urgency=85,
            risk=30,
            tasks=[
                MissionTaskInput(key="plan", title="Plan rollout", duration_hours=6, required_capabilities=["planning"]),
                MissionTaskInput(key="build", title="Build capability", duration_hours=12, required_capabilities=["implementation"], dependency_keys=["plan"]),
                MissionTaskInput(key="test", title="Validate capability", duration_hours=6, required_capabilities=["testing"], dependency_keys=["build"]),
            ],
        )],
    )


def test_analysis_assigns_agents_and_builds_dependency_schedule():
    service = ExecutiveMissionOrchestrationService()
    record = service.create(payload())
    analyzed = service.analyze(record.id, "workspace-a", "analyst-1")
    assert analyzed.status == OrchestrationStatus.pending_approval
    assert analyzed.analysis is not None
    assert [item.task_key for item in analyzed.analysis.task_schedule] == ["plan", "build", "test"]
    assert analyzed.analysis.task_schedule[1].start_hour >= analyzed.analysis.task_schedule[0].end_hour
    assert all(item.assigned_agent_id for item in analyzed.analysis.assignments)
    assert analyzed.analysis.autonomous_execution_enabled is False


def test_owner_cannot_self_approve():
    service = ExecutiveMissionOrchestrationService()
    record = service.create(payload())
    service.analyze(record.id, "workspace-a", "analyst-1")
    with pytest.raises(ValueError, match="cannot approve"):
        service.approve(record.id, ApprovalRequest(workspace_id="workspace-a", reviewer_id="owner-1", decision=ApprovalDecision.approve, reason="Self approval is forbidden"))


def test_independent_reviewer_can_approve():
    service = ExecutiveMissionOrchestrationService()
    record = service.create(payload())
    service.analyze(record.id, "workspace-a", "analyst-1")
    approved = service.approve(record.id, ApprovalRequest(workspace_id="workspace-a", reviewer_id="reviewer-2", decision=ApprovalDecision.approve, reason="Capacity and dependencies reviewed"))
    assert approved.status == OrchestrationStatus.approved
    assert approved.approved_by == "reviewer-2"


def test_workspace_isolation_and_duplicate_protection():
    service = ExecutiveMissionOrchestrationService()
    record = service.create(payload("workspace-a"))
    assert service.get(record.id, "workspace-b") is None
    assert service.list_records("workspace-b") == []
    with pytest.raises(ValueError, match="already exists"):
        service.create(payload("workspace-a"))


def test_missing_capacity_defers_task_without_execution():
    service = ExecutiveMissionOrchestrationService()
    request = payload()
    request.agents = []
    record = service.create(request)
    analyzed = service.analyze(record.id, "workspace-a", "analyst-1")
    assert analyzed.analysis is not None
    assert analyzed.analysis.deferred_tasks
    assert analyzed.analysis.horizon_fit is False
    assert all(item.requires_human_approval for item in analyzed.analysis.task_schedule)
