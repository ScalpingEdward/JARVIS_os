from datetime import datetime, timezone
from uuid import UUID

from ..company_runtime.models import RuntimeMissionCreate, RuntimeStatus
from ..company_runtime.service import company_runtime_service
from ..strategic_planner.models import MilestoneState, MilestoneUpdate, PlanState
from ..strategic_planner.service import strategic_planner_service
from .models import BridgeApproval, BridgeCreate, BridgeRecord, BridgeState, BridgeStatus, ExecutionLink


class GoalExecutionService:
    def __init__(self) -> None:
        self._bridges: dict[UUID, BridgeRecord] = {}

    def reset(self) -> None:
        self._bridges.clear()

    def create(self, payload: BridgeCreate) -> BridgeRecord:
        plan = strategic_planner_service.get(payload.plan_id)
        if plan is None:
            raise LookupError("Strategic plan not found")
        if plan.state not in {PlanState.active, PlanState.at_risk}:
            raise ValueError("Only active or at-risk plans can be bridged")
        if any(item.plan_id == plan.id for item in self._bridges.values()):
            raise ValueError("Plan already has an execution bridge")

        record = BridgeRecord(plan_id=plan.id, approved_by=payload.approved_by)
        if payload.approved_by:
            self._materialize(record, payload)
        self._bridges[record.id] = record
        return record

    def approve(self, bridge_id: UUID, payload: BridgeApproval) -> BridgeRecord | None:
        record = self._bridges.get(bridge_id)
        if record is None:
            return None
        if record.state != BridgeState.awaiting_approval:
            raise ValueError("Bridge is not awaiting approval")
        record.approved_by = payload.approved_by
        self._materialize(record, BridgeCreate(plan_id=record.plan_id, approved_by=payload.approved_by))
        return record

    def _materialize(self, record: BridgeRecord, payload: BridgeCreate) -> None:
        plan = strategic_planner_service.get(record.plan_id)
        if plan is None:
            raise LookupError("Strategic plan not found")

        title_map = {item.title: item.id for item in plan.milestones}
        mission_map: dict[UUID, UUID] = {}
        links: list[ExecutionLink] = []
        for milestone in plan.milestones:
            mission = company_runtime_service.create(
                RuntimeMissionCreate(
                    title=f"{plan.title}: {milestone.title}",
                    objective=milestone.description or f"Complete milestone: {milestone.title}",
                    priority=milestone.priority,
                    token_limit=payload.default_token_limit,
                    cost_limit_usd=payload.default_cost_limit_usd,
                    runtime_limit_seconds=payload.default_runtime_limit_seconds,
                    max_retries=payload.default_max_retries,
                )
            )
            mission_map[milestone.id] = mission.id

        for milestone in plan.milestones:
            dependency_ids = [title_map[name] for name in milestone.dependencies if name in title_map]
            links.append(
                ExecutionLink(
                    milestone_id=milestone.id,
                    mission_id=mission_map[milestone.id],
                    dependencies=[mission_map[item] for item in dependency_ids],
                    assigned_agent=payload.agent_map.get(milestone.title),
                )
            )
            strategic_planner_service.update_milestone(
                plan.id,
                milestone.id,
                MilestoneUpdate(state=MilestoneState.ready, progress=milestone.progress),
            )

        record.links = links
        record.state = BridgeState.active
        record.updated_at = datetime.now(timezone.utc)
        self.sync(record.id)

    def sync(self, bridge_id: UUID) -> BridgeRecord | None:
        record = self._bridges.get(bridge_id)
        if record is None:
            return None
        plan = strategic_planner_service.get(record.plan_id)
        if plan is None:
            record.state = BridgeState.blocked
            record.blocker = "Strategic plan missing"
            return record

        for link in record.links:
            mission = company_runtime_service.get(link.mission_id)
            if mission is None:
                link.blocker = "Runtime mission missing"
                continue
            link.progress = 1 if mission.status == RuntimeStatus.completed else 0
            if mission.status in {RuntimeStatus.failed, RuntimeStatus.dead_letter, RuntimeStatus.blocked}:
                link.blocker = f"Mission status: {mission.status.value}"
                strategic_planner_service.update_milestone(
                    plan.id, link.milestone_id, MilestoneUpdate(state=MilestoneState.blocked, blocker=link.blocker)
                )
            elif mission.status == RuntimeStatus.completed:
                link.blocker = None
                strategic_planner_service.update_milestone(
                    plan.id, link.milestone_id, MilestoneUpdate(state=MilestoneState.completed, progress=1)
                )
            elif mission.status in {RuntimeStatus.assigned, RuntimeStatus.working, RuntimeStatus.waiting_review, RuntimeStatus.waiting_approval}:
                strategic_planner_service.update_milestone(
                    plan.id, link.milestone_id, MilestoneUpdate(state=MilestoneState.active)
                )

        record.progress = round(sum(item.progress for item in record.links) / len(record.links), 4) if record.links else 0
        blocked = [item for item in record.links if item.blocker]
        if record.progress >= 1:
            record.state = BridgeState.completed
            record.blocker = None
        elif blocked:
            record.state = BridgeState.blocked
            record.blocker = blocked[0].blocker
        else:
            record.state = BridgeState.active
            record.blocker = None
        record.updated_at = datetime.now(timezone.utc)
        return record

    def get(self, bridge_id: UUID) -> BridgeRecord | None:
        return self._bridges.get(bridge_id)

    def list_all(self) -> list[BridgeRecord]:
        return list(self._bridges.values())

    def status(self) -> BridgeStatus:
        values = self.list_all()
        return BridgeStatus(
            total=len(values),
            awaiting_approval=sum(item.state == BridgeState.awaiting_approval for item in values),
            active=sum(item.state == BridgeState.active for item in values),
            blocked=sum(item.state == BridgeState.blocked for item in values),
            completed=sum(item.state == BridgeState.completed for item in values),
        )


goal_execution_service = GoalExecutionService()
