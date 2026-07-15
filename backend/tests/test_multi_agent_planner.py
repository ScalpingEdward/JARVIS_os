import pytest

from app.planner.api import plan_progress
from app.planner.models import PlanGoal, StepStatus, WorkerPreference
from app.planner.service import PlannerError, planner_service


def setup_function() -> None:
    planner_service.reset()


def test_large_goal_becomes_dependency_aware_multi_agent_plan() -> None:
    plan = planner_service.create_plan(
        PlanGoal(
            goal="Build a Telegram trading signal platform with dashboard, tests and deployment",
            constraints=["No automatic trading without approval", "Secrets must remain outside source control"],
        )
    )

    assert len(plan.steps) >= 7
    assert plan.steps[0].status == StepStatus.ready
    assert all(step.reviewer_worker is not None for step in plan.steps)
    assert any(step.preferred_worker == WorkerPreference.codex for step in plan.steps)
    assert any(step.preferred_worker == WorkerPreference.claude for step in plan.steps)
    assert any(step.approval_required for step in plan.steps)
    assert plan.constraints[0] == "No automatic trading without approval"


def test_dependencies_block_early_execution_and_unlock_next_step() -> None:
    plan = planner_service.create_plan(PlanGoal(goal="Build a secure project management API"))
    first, second = plan.steps[0], plan.steps[1]

    with pytest.raises(PlannerError, match="dependencies"):
        planner_service.update_step(plan.id, second.id, StepStatus.in_progress)

    planner_service.update_step(plan.id, first.id, StepStatus.completed)
    updated = planner_service.get(plan.id)
    unlocked = next(step for step in updated.steps if step.id == second.id)
    assert unlocked.status == StepStatus.ready


def test_progress_reaches_completed_only_after_all_steps_finish() -> None:
    plan = planner_service.create_plan(
        PlanGoal(
            goal="Build backend service",
            include_frontend=False,
            include_deployment=False,
            include_documentation=False,
        )
    )
    for step in plan.steps:
        planner_service.update_step(plan.id, step.id, StepStatus.completed)

    progress = planner_service.progress(plan.id)
    assert progress.progress_percent == 100
    assert progress.completed_steps == progress.total_steps
    assert progress.status == "completed"


def test_api_progress_contract() -> None:
    plan = planner_service.create_plan(
        PlanGoal(goal="Build a multi-agent coding workspace", include_deployment=False)
    )
    response = plan_progress(plan.id)
    assert response.total_steps >= 6
    assert response.progress_percent == 0
