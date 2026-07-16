from datetime import datetime, timezone
from uuid import UUID

from .models import (
    MilestoneRecord,
    MilestoneState,
    MilestoneUpdate,
    PlanActivation,
    PlanState,
    StrategicPlanCreate,
    StrategicPlanRecord,
    StrategicPlannerStatus,
)


class StrategicPlannerService:
    def __init__(self) -> None:
        self._plans: dict[UUID, StrategicPlanRecord] = {}

    def reset(self) -> None:
        self._plans.clear()

    def create(self, payload: StrategicPlanCreate) -> StrategicPlanRecord:
        milestones = [MilestoneRecord(**item.model_dump()) for item in payload.milestones]
        plan = StrategicPlanRecord(**payload.model_dump(exclude={"milestones"}), milestones=milestones)
        self._recalculate(plan)
        self._plans[plan.id] = plan
        return plan

    def list_all(self) -> list[StrategicPlanRecord]:
        return sorted(self._plans.values(), key=lambda item: (item.state != PlanState.active, item.priority, item.created_at))

    def get(self, plan_id: UUID) -> StrategicPlanRecord | None:
        return self._plans.get(plan_id)

    def activate(self, plan_id: UUID, payload: PlanActivation) -> StrategicPlanRecord | None:
        plan = self.get(plan_id)
        if plan is None:
            return None
        plan.state = PlanState.active
        plan.updated_at = datetime.now(timezone.utc)
        self._recalculate(plan)
        return plan

    def update_milestone(self, plan_id: UUID, milestone_id: UUID, payload: MilestoneUpdate) -> StrategicPlanRecord | None:
        plan = self.get(plan_id)
        if plan is None:
            return None
        milestone = next((item for item in plan.milestones if item.id == milestone_id), None)
        if milestone is None:
            return None
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(milestone, key, value)
        if milestone.state == MilestoneState.completed:
            milestone.progress = 1
            milestone.blocker = None
        elif milestone.blocker:
            milestone.state = MilestoneState.blocked
        plan.updated_at = datetime.now(timezone.utc)
        self._recalculate(plan)
        return plan

    def _recalculate(self, plan: StrategicPlanRecord) -> None:
        if plan.milestones:
            plan.progress = round(sum(item.progress for item in plan.milestones) / len(plan.milestones), 4)
        else:
            plan.progress = 0

        blocked = [item for item in plan.milestones if item.state == MilestoneState.blocked]
        if plan.progress >= 1:
            plan.state = PlanState.completed
        elif blocked:
            plan.state = PlanState.blocked if len(blocked) == len(plan.milestones) else PlanState.at_risk
        elif plan.state not in {PlanState.draft, PlanState.archived}:
            plan.state = PlanState.active

        available_ratio = []
        for milestone in plan.milestones:
            for resource in milestone.resources:
                available_ratio.append(1 if resource.amount == 0 else min(resource.available / resource.amount, 1))
        resource_confidence = sum(available_ratio) / len(available_ratio) if available_ratio else 0.75
        risk_penalty = sum(risk.probability * risk.impact for risk in plan.risks) / max(len(plan.risks), 1)
        assumption_factor = 0.8 if plan.assumptions else 0.65
        plan.confidence = round(max(0, min(1, (resource_confidence * 0.5 + assumption_factor * 0.5) - risk_penalty * 0.4)), 4)

        ready = [item for item in plan.milestones if item.state in {MilestoneState.ready, MilestoneState.active, MilestoneState.planned}]
        ready.sort(key=lambda item: (item.priority, item.target_date is None, item.target_date))
        plan.recommended_focus = [item.id for item in ready[:3]]

    def status(self) -> StrategicPlannerStatus:
        plans = list(self._plans.values())
        average = sum(item.progress for item in plans) / len(plans) if plans else 0
        return StrategicPlannerStatus(
            total_plans=len(plans),
            active=sum(item.state == PlanState.active for item in plans),
            at_risk=sum(item.state == PlanState.at_risk for item in plans),
            blocked=sum(item.state == PlanState.blocked for item in plans),
            completed=sum(item.state == PlanState.completed for item in plans),
            average_progress=round(average, 4),
        )


strategic_planner_service = StrategicPlannerService()
