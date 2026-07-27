import pytest

from app.schemas.autonomous_task_planner import TaskPlanAction, TaskPlanCreate
from app.services.autonomous_task_planner import AutonomousTaskPlannerService


def payload(**goal_overrides):
    goal = {
        "goal_id": "goal-1",
        "objective": "Prepare a validated operational optimization plan",
        "required_capabilities": ["analysis", "validation"],
        "required_tools": ["github-read"],
        "required_data_domains": ["operations"],
        "success_criteria": ["plan is complete", "no execution occurs"],
        "max_tasks": 4,
        "max_parallel_tasks": 2,
        "max_total_budget": 20.0,
        "criticality": 0.7,
    }
    goal.update(goal_overrides)
    return TaskPlanCreate(
        workspace_id="ws-a",
        source_key="planner-source",
        requested_by="operator",
        goal=goal,
        tasks=[
            {
                "task_id": "t1",
                "title": "Analyze",
                "description": "Analyze candidate",
                "required_capabilities": ["analysis"],
                "required_tools": ["github-read"],
                "required_data_domains": ["operations"],
                "estimated_budget": 5.0,
            },
            {
                "task_id": "t2",
                "title": "Validate",
                "description": "Validate findings",
                "required_capabilities": ["validation"],
                "depends_on": ["t1"],
                "estimated_budget": 5.0,
            },
        ],
    )


def test_status_keeps_execution_disabled():
    status = AutonomousTaskPlannerService().status()
    assert status["version"] == "21.114"
    assert status["planning_enabled"] is True
    assert status["task_execution_enabled"] is False
    assert status["tool_execution_enabled"] is False
    assert status["agent_dispatch_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_plan_can_be_approved_and_marked_ready():
    service = AutonomousTaskPlannerService()
    record = service.create(payload())
    assert record.state.value == "planned"
    record = service.act(record.record_id, TaskPlanAction(workspace_id="ws-a", action="approve", actor="owner", operation_id="op-1"))
    record = service.act(record.record_id, TaskPlanAction(workspace_id="ws-a", action="mark-ready", actor="owner", operation_id="op-2"))
    assert record.state.value == "ready"
    assert record.approved_by == "owner"


def test_execution_permission_is_flagged_and_blocks_approval():
    p = payload()
    p.tasks[0].execution_allowed = True
    service = AutonomousTaskPlannerService()
    record = service.create(p)
    assert "execution-permission-present" in record.risk_flags
    with pytest.raises(ValueError, match="findings block approval"):
        service.act(record.record_id, TaskPlanAction(workspace_id="ws-a", action="approve", actor="owner", operation_id="op-a"))


def test_critical_execution_permission_triggers_hard_block():
    p = payload(criticality=0.98)
    p.tasks[0].execution_allowed = True
    service = AutonomousTaskPlannerService()
    record = service.create(p)
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_replay_and_workspace_isolation():
    service = AutonomousTaskPlannerService()
    record = service.create(payload())
    service.act(record.record_id, TaskPlanAction(workspace_id="ws-a", action="submit-review", actor="reviewer", operation_id="same-op"))
    with pytest.raises(ValueError, match="replay"):
        service.act(record.record_id, TaskPlanAction(workspace_id="ws-a", action="approve", actor="reviewer", operation_id="same-op"))
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_rejected():
    service = AutonomousTaskPlannerService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
