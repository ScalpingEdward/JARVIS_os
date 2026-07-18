import pytest

from app.mission_control.models import AgentRegistration, AgentRole, MissionAction, MissionCreate, MissionState, MissionTask, TaskState
from app.mission_control.service import MissionControlError, mission_control_service


@pytest.fixture(autouse=True)
def reset_service():
    mission_control_service.reset()
    yield
    mission_control_service.reset()


def _agent(workspace: str = "ws-1"):
    return mission_control_service.register_agent(AgentRegistration(
        workspace_id=workspace,
        agent_key="developer-1",
        name="Developer Agent",
        role=AgentRole.DEVELOPER,
        capabilities=["python", "tests"],
    ))


def _mission(workspace: str = "ws-1"):
    return mission_control_service.create_mission(MissionCreate(
        workspace_id=workspace,
        owner_id="owner-1",
        mission_key="mission-alpha",
        name="Mission Alpha",
        objective="Build and verify a governed module",
        token_budget=5000,
        cost_budget=20,
        tasks=[
            MissionTask(key="build", name="Build", required_role=AgentRole.DEVELOPER, required_capabilities=["python"], estimated_tokens=1000, estimated_cost=2),
            MissionTask(key="test", name="Test", required_role=AgentRole.DEVELOPER, required_capabilities=["tests"], depends_on=["build"], requires_human_approval=True, estimated_tokens=500, estimated_cost=1),
        ],
    ))


def test_mission_lifecycle_assignment_and_dependencies():
    _agent()
    mission = _mission()
    mission_control_service.plan(mission.id, "ws-1", MissionAction(actor_id="owner-1"))
    mission_control_service.approve(mission.id, "ws-1", MissionAction(actor_id="reviewer-1"))
    mission = mission_control_service.start(mission.id, "ws-1", MissionAction(actor_id="operator-1"))
    assert mission.state == MissionState.RUNNING
    assert mission.runtime[0].state == TaskState.ASSIGNED
    assert mission.runtime[1].state == TaskState.BLOCKED

    mission = mission_control_service.complete_task(mission.id, "build", "ws-1", MissionAction(actor_id="operator-1"))
    assert mission.runtime[1].state == TaskState.WAITING_APPROVAL
    mission = mission_control_service.complete_task(mission.id, "test", "ws-1", MissionAction(actor_id="approver-1"))
    assert mission.state == MissionState.COMPLETED


def test_owner_cannot_self_approve():
    mission = _mission()
    mission_control_service.plan(mission.id, "ws-1", MissionAction(actor_id="owner-1"))
    with pytest.raises(MissionControlError, match="self-approve"):
        mission_control_service.approve(mission.id, "ws-1", MissionAction(actor_id="owner-1"))


def test_workspace_isolation():
    mission = _mission()
    with pytest.raises(MissionControlError, match="not found"):
        mission_control_service.get_mission(mission.id, "ws-2")


def test_duplicate_keys_and_external_actions_are_blocked():
    _mission()
    with pytest.raises(MissionControlError, match="mission key"):
        _mission()
    with pytest.raises(ValueError, match="automatic external actions"):
        MissionTask(key="unsafe", name="Unsafe", required_role=AgentRole.OPERATOR, automatic_external_action=True)


def test_status_and_audit_are_workspace_scoped():
    _agent()
    mission = _mission()
    assert mission_control_service.status().total_missions == 1
    assert mission_control_service.audit("ws-1")
    assert mission_control_service.audit("ws-2") == []
