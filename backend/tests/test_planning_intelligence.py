import pytest

from app.planning_intelligence.models import (
    ApprovalRequest,
    Constraint,
    GoalCreate,
    Objective,
    PlanCreate,
    PlanOption,
    PlanState,
    RiskLevel,
    SimulationRequest,
)
from app.planning_intelligence.service import PlanningIntelligenceService


@pytest.fixture
def service() -> PlanningIntelligenceService:
    return PlanningIntelligenceService()


def _goal(service: PlanningIntelligenceService, workspace: str = "alpha"):
    return service.create_goal(
        GoalCreate(
            workspace_id=workspace,
            owner_id="owner-1",
            key="launch.jarvis",
            title="Launch governed JARVIS capability",
            objectives=[Objective(key="quality", title="Quality", success_metric="tests pass")],
            constraints=[Constraint(key="human", description="Human approval required")],
        )
    )


def _plan(service: PlanningIntelligenceService, workspace: str = "alpha"):
    goal = _goal(service, workspace)
    return service.create_plan(
        PlanCreate(
            workspace_id=workspace,
            owner_id="owner-1",
            goal_id=goal.id,
            key="launch.plan",
            title="Launch plan",
            max_cost=100,
            max_duration_minutes=120,
            options=[
                PlanOption(
                    key="safe",
                    title="Safe rollout",
                    summary="Controlled rollout",
                    steps=["review", "simulate", "approve"],
                    estimated_cost=50,
                    estimated_duration_minutes=60,
                    risk_level=RiskLevel.LOW,
                    rollback_plan=["restore previous version"],
                ),
                PlanOption(
                    key="fast",
                    title="Fast rollout",
                    summary="Accelerated rollout",
                    steps=["deploy"],
                    estimated_cost=150,
                    estimated_duration_minutes=30,
                    risk_level=RiskLevel.HIGH,
                ),
            ],
        )
    )


def test_simulation_recommends_feasible_option(service: PlanningIntelligenceService) -> None:
    plan = _plan(service)
    simulation = service.simulate(
        plan.id,
        SimulationRequest(workspace_id="alpha", actor_id="planner-1"),
    )
    assert simulation.recommended_option_key == "safe"
    assert service.get_plan("alpha", plan.id).state == PlanState.SIMULATED
    assert any(not item.feasible for item in simulation.evaluations if item.option_key == "fast")


def test_owner_cannot_self_approve(service: PlanningIntelligenceService) -> None:
    plan = _plan(service)
    service.simulate(plan.id, SimulationRequest(workspace_id="alpha", actor_id="planner-1"))
    with pytest.raises(ValueError, match="self-approve"):
        service.approve(
            plan.id,
            ApprovalRequest(workspace_id="alpha", reviewer_id="owner-1", selected_option_key="safe"),
        )


def test_independent_approval_sets_execution_ready(service: PlanningIntelligenceService) -> None:
    plan = _plan(service)
    service.simulate(plan.id, SimulationRequest(workspace_id="alpha", actor_id="planner-1"))
    approved = service.approve(
        plan.id,
        ApprovalRequest(workspace_id="alpha", reviewer_id="reviewer-2", selected_option_key="safe"),
    )
    assert approved.state == PlanState.EXECUTION_READY
    assert approved.approved_by == "reviewer-2"
    assert service.status("alpha").execution_ready_plans == 1


def test_workspace_isolation(service: PlanningIntelligenceService) -> None:
    plan = _plan(service, "alpha")
    assert service.get_plan("beta", plan.id) is None
    assert service.list_goals("beta") == []
    with pytest.raises(ValueError, match="plan not found"):
        service.simulate(plan.id, SimulationRequest(workspace_id="beta", actor_id="planner"))


def test_duplicate_keys_are_rejected(service: PlanningIntelligenceService) -> None:
    _goal(service)
    with pytest.raises(ValueError, match="already exists"):
        _goal(service)


def test_automatic_external_action_is_rejected() -> None:
    with pytest.raises(ValueError, match="automatic external actions"):
        GoalCreate(
            workspace_id="alpha",
            owner_id="owner",
            key="unsafe",
            title="Unsafe",
            objectives=[Objective(key="x", title="X", success_metric="x")],
            automatic_external_action=True,
        )
