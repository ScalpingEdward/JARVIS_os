from datetime import datetime, timedelta, timezone

import pytest

from app.planning_intelligence.models import (
    ApprovalRequest,
    Constraint,
    GoalCreate,
    Milestone,
    Objective,
    ObjectiveContribution,
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
            objectives=[
                Objective(key="quality", title="Quality", weight=70, success_metric="tests pass"),
                Objective(key="speed", title="Speed", weight=30, success_metric="lead time"),
            ],
            constraints=[Constraint(key="human", description="Human approval required")],
            milestones=[
                Milestone(
                    key="release",
                    title="Release candidate",
                    due_at=datetime.now(timezone.utc) + timedelta(days=7),
                    required_objective_keys=["quality"],
                )
            ],
            budget=100,
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
            mission_template_key="jarvis.release",
            options=[
                PlanOption(
                    key="safe",
                    title="Safe rollout",
                    summary="Controlled rollout",
                    steps=["review", "simulate", "approve"],
                    required_capabilities=["testing", "review"],
                    objective_contributions=[
                        ObjectiveContribution(objective_key="quality", score=1.0),
                        ObjectiveContribution(objective_key="speed", score=0.6),
                    ],
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
                    objective_contributions=[
                        ObjectiveContribution(objective_key="quality", score=0.4),
                        ObjectiveContribution(objective_key="speed", score=1.0),
                    ],
                    estimated_cost=150,
                    estimated_duration_minutes=30,
                    risk_level=RiskLevel.HIGH,
                ),
            ],
        )
    )


def test_simulation_recommends_feasible_option_and_runs_sensitivity(service: PlanningIntelligenceService) -> None:
    plan = _plan(service)
    simulation = service.simulate(plan.id, SimulationRequest(workspace_id="alpha", actor_id="planner-1"))
    assert simulation.recommended_option_key == "safe"
    assert len(simulation.sensitivity) == 8
    assert service.get_plan("alpha", plan.id).state == PlanState.SIMULATED
    assert any(not item.feasible for item in simulation.evaluations if item.option_key == "fast")


def test_hierarchical_goal_tree(service: PlanningIntelligenceService) -> None:
    root = _goal(service)
    child = service.create_goal(
        GoalCreate(
            workspace_id="alpha",
            owner_id="owner-1",
            key="launch.jarvis.backend",
            title="Backend launch",
            parent_goal_id=root.id,
            dependency_goal_ids=[],
            objectives=[Objective(key="api", title="API", success_metric="healthy")],
        )
    )
    assert [item.id for item in service.goal_tree("alpha", root.id)] == [root.id, child.id]


def test_cross_workspace_goal_reference_rejected(service: PlanningIntelligenceService) -> None:
    foreign = _goal(service, "beta")
    with pytest.raises(ValueError, match="referenced goal"):
        service.create_goal(
            GoalCreate(
                workspace_id="alpha",
                owner_id="owner",
                key="bad.child",
                title="Bad child",
                parent_goal_id=foreign.id,
                objectives=[Objective(key="x", title="X", success_metric="x")],
            )
        )


def test_owner_cannot_self_approve(service: PlanningIntelligenceService) -> None:
    plan = _plan(service)
    service.simulate(plan.id, SimulationRequest(workspace_id="alpha", actor_id="planner-1"))
    with pytest.raises(ValueError, match="self-approve"):
        service.approve(plan.id, ApprovalRequest(workspace_id="alpha", reviewer_id="owner-1", selected_option_key="safe"))


def test_independent_approval_enables_non_executing_handoff_preview(service: PlanningIntelligenceService) -> None:
    plan = _plan(service)
    service.simulate(plan.id, SimulationRequest(workspace_id="alpha", actor_id="planner-1"))
    approved = service.approve(
        plan.id,
        ApprovalRequest(workspace_id="alpha", reviewer_id="reviewer-2", selected_option_key="safe"),
    )
    preview = service.mission_handoff_preview("alpha", plan.id)
    assert approved.state == PlanState.EXECUTION_READY
    assert preview.mission_template_key == "jarvis.release"
    assert preview.tasks == ["review", "simulate", "approve"]
    assert preview.execution_triggered is False
    assert service.status("alpha").execution_ready_plans == 1


def test_handoff_preview_requires_approval(service: PlanningIntelligenceService) -> None:
    plan = _plan(service)
    with pytest.raises(ValueError, match="execution-ready"):
        service.mission_handoff_preview("alpha", plan.id)


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


def test_unknown_objective_contribution_is_rejected(service: PlanningIntelligenceService) -> None:
    goal = _goal(service)
    with pytest.raises(ValueError, match="goal objectives"):
        service.create_plan(
            PlanCreate(
                workspace_id="alpha",
                owner_id="owner",
                goal_id=goal.id,
                key="bad.plan",
                title="Bad plan",
                options=[
                    PlanOption(
                        key="a",
                        title="A",
                        summary="A",
                        steps=["a"],
                        objective_contributions=[ObjectiveContribution(objective_key="missing", score=1)],
                    ),
                    PlanOption(key="b", title="B", summary="B", steps=["b"]),
                ],
            )
        )


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
