from datetime import datetime, timezone

from app.strategic_planning.models import GoalDomain, GoalStatus, ProgressUpdate, StrategicGoalCreate
from app.strategic_planning.service import strategic_planning_service


def setup_function() -> None:
    strategic_planning_service.reset()


def test_goal_is_human_gated_and_owned_by_master_brano() -> None:
    goal = strategic_planning_service.create(
        StrategicGoalCreate(title="Protect funded capital", domain=GoalDomain.trading, priority=95)
    )
    assert goal.owner_name == "MASTER Brano"
    assert goal.automatic_execution is False
    assert strategic_planning_service.status().automatic_order_execution is False


def test_plan_prioritizes_high_value_goals_and_detects_conflicts() -> None:
    deadline = datetime(2026, 8, 1, tzinfo=timezone.utc)
    first = strategic_planning_service.create(
        StrategicGoalCreate(title="Complete FTMO verification", domain=GoalDomain.trading, priority=95, target_date=deadline)
    )
    second = strategic_planning_service.create(
        StrategicGoalCreate(title="Launch PHOENIX locally", domain=GoalDomain.engineering, priority=90, target_date=deadline)
    )
    plan = strategic_planning_service.plan()
    assert plan.top_priorities[0] == first.id
    assert second.id in plan.top_priorities
    assert plan.conflicts
    assert plan.requires_human_approval is True
    assert plan.automatic_execution is False


def test_progress_update_completes_goal() -> None:
    goal = strategic_planning_service.create(
        StrategicGoalCreate(title="Configure Telegram connector", domain=GoalDomain.engineering)
    )
    updated = strategic_planning_service.update_progress(goal.id, ProgressUpdate(progress=1.0))
    assert updated is not None
    assert updated.status == GoalStatus.completed
    assert strategic_planning_service.status().completed == 1
