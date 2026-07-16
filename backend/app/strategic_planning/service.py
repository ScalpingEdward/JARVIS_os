from datetime import datetime, timezone
from uuid import UUID

from .models import GoalStatus, ProgressUpdate, StrategicGoal, StrategicGoalCreate, StrategicPlan, StrategicPlanningStatus


class StrategicPlanningService:
    def __init__(self) -> None:
        self._goals: dict[UUID, StrategicGoal] = {}

    def reset(self) -> None:
        self._goals.clear()

    def create(self, payload: StrategicGoalCreate) -> StrategicGoal:
        goal = StrategicGoal(**payload.model_dump())
        self._goals[goal.id] = goal
        return goal

    def list_all(self) -> list[StrategicGoal]:
        return sorted(self._goals.values(), key=lambda goal: (-goal.priority, goal.created_at))

    def get(self, goal_id: UUID) -> StrategicGoal | None:
        return self._goals.get(goal_id)

    def update_progress(self, goal_id: UUID, payload: ProgressUpdate) -> StrategicGoal | None:
        goal = self._goals.get(goal_id)
        if goal is None:
            return None
        goal.progress = payload.progress
        goal.status = payload.status or (GoalStatus.completed if payload.progress >= 1 else GoalStatus.active)
        goal.updated_at = datetime.now(timezone.utc)
        return goal

    def plan(self) -> StrategicPlan:
        goals = self.list_all()
        active = [goal for goal in goals if goal.status in {GoalStatus.active, GoalStatus.planned, GoalStatus.blocked}]
        top = [goal.id for goal in active[:5]]
        blockers = [f"{goal.title}: blocked" for goal in goals if goal.status == GoalStatus.blocked]
        conflicts: list[str] = []
        for index, left in enumerate(active):
            for right in active[index + 1:]:
                if left.target_date and right.target_date and left.target_date.date() == right.target_date.date() and left.priority >= 80 and right.priority >= 80:
                    conflicts.append(f"High-priority deadline conflict: {left.title} vs {right.title}")
        recommendations = [f"Focus next on: {goal.title}" for goal in active[:3]]
        if not recommendations:
            recommendations.append("Define the next strategic goal for MASTER Brano.")
        return StrategicPlan(goals=goals, top_priorities=top, conflicts=conflicts, blockers=blockers, recommendations=recommendations)

    def status(self) -> StrategicPlanningStatus:
        goals = list(self._goals.values())
        return StrategicPlanningStatus(
            goals=len(goals),
            active=sum(goal.status == GoalStatus.active for goal in goals),
            blocked=sum(goal.status == GoalStatus.blocked for goal in goals),
            completed=sum(goal.status == GoalStatus.completed for goal in goals),
        )


strategic_planning_service = StrategicPlanningService()
