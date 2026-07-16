from __future__ import annotations

from uuid import UUID

from .models import (
    AgentState,
    CompanyAgent,
    CompanyRole,
    CompanyStatus,
    MissionCreate,
    MissionDetail,
    MissionRecord,
    WorkItem,
    WorkStatus,
)


class CompanyService:
    def __init__(self) -> None:
        self.agents = self._default_agents()
        self.missions: dict[UUID, MissionRecord] = {}
        self.work_items: dict[UUID, WorkItem] = {}

    def reset(self) -> None:
        self.__init__()

    def _default_agents(self) -> list[CompanyAgent]:
        definitions = {
            CompanyRole.CEO: ("PHOENIX CEO", ["planning", "delegation", "escalation"]),
            CompanyRole.QUANT: ("Quant", ["statistics", "backtesting", "risk-models"]),
            CompanyRole.TRADING: ("Trading", ["market-structure", "execution-review", "journal"]),
            CompanyRole.RESEARCH: ("Research", ["public-sources", "market-radar", "synthesis"]),
            CompanyRole.BACKEND: ("Backend", ["python", "apis", "databases"]),
            CompanyRole.FRONTEND: ("Frontend", ["ui", "responsive-design", "visualization"]),
            CompanyRole.QA: ("QA", ["testing", "acceptance-criteria", "regression"]),
            CompanyRole.SECURITY: ("Security", ["threat-modeling", "permissions", "secrets"]),
            CompanyRole.BUSINESS: ("Business", ["strategy", "ecommerce", "operations"]),
        }
        return [CompanyAgent(name=name, role=role, capabilities=caps) for role, (name, caps) in definitions.items()]

    def list_agents(self) -> list[CompanyAgent]:
        return self.agents

    def create_mission(self, payload: MissionCreate) -> MissionDetail:
        mission = MissionRecord(**payload.model_dump())
        self.missions[mission.id] = mission
        items = self._build_plan(mission)
        for item in items:
            self.work_items[item.id] = item
        self._refresh(mission.id)
        return self.get_mission(mission.id)

    def _build_plan(self, mission: MissionRecord) -> list[WorkItem]:
        research = WorkItem(
            mission_id=mission.id,
            title="Research requirements and constraints",
            owner_role=CompanyRole.RESEARCH,
            reviewer_role=CompanyRole.CEO,
        )
        architecture = WorkItem(
            mission_id=mission.id,
            title="Design architecture and implementation plan",
            owner_role=CompanyRole.BACKEND,
            reviewer_role=CompanyRole.SECURITY,
            depends_on=[research.id],
        )
        implementation = WorkItem(
            mission_id=mission.id,
            title="Implement approved solution",
            owner_role=CompanyRole.BACKEND,
            reviewer_role=CompanyRole.QA,
            depends_on=[architecture.id],
        )
        qa = WorkItem(
            mission_id=mission.id,
            title="Run QA and regression review",
            owner_role=CompanyRole.QA,
            reviewer_role=CompanyRole.SECURITY,
            depends_on=[implementation.id],
        )
        release = WorkItem(
            mission_id=mission.id,
            title="Prepare release recommendation",
            owner_role=CompanyRole.CEO,
            reviewer_role=CompanyRole.SECURITY,
            depends_on=[qa.id],
            requires_human_approval=True,
        )
        return [research, architecture, implementation, qa, release]

    def get_mission(self, mission_id: UUID) -> MissionDetail:
        mission = self.missions[mission_id]
        items = [item for item in self.work_items.values() if item.mission_id == mission_id]
        completed = sum(item.status == WorkStatus.COMPLETED for item in items)
        return MissionDetail(
            mission=mission,
            work_items=items,
            completion_percent=int(completed / len(items) * 100) if items else 0,
            ready_count=sum(item.status == WorkStatus.READY for item in items),
            blocked_count=sum(item.status == WorkStatus.BLOCKED for item in items),
        )

    def list_missions(self) -> list[MissionDetail]:
        return [self.get_mission(mission_id) for mission_id in self.missions]

    def update_work_item(self, work_item_id: UUID, status: WorkStatus, result_summary: str | None) -> WorkItem:
        item = self.work_items[work_item_id]
        if item.requires_human_approval and status == WorkStatus.COMPLETED:
            item.status = WorkStatus.REVIEW
            item.result_summary = result_summary or "Awaiting human approval"
        else:
            item.status = status
            item.result_summary = result_summary
        self._refresh(item.mission_id)
        return item

    def _refresh(self, mission_id: UUID) -> None:
        items = [item for item in self.work_items.values() if item.mission_id == mission_id]
        by_id = {item.id: item for item in items}
        for item in items:
            if item.status in {WorkStatus.COMPLETED, WorkStatus.IN_PROGRESS, WorkStatus.REVIEW, WorkStatus.REJECTED}:
                continue
            dependencies = [by_id[dependency].status for dependency in item.depends_on]
            item.status = WorkStatus.READY if all(state == WorkStatus.COMPLETED for state in dependencies) else WorkStatus.BLOCKED
        mission = self.missions[mission_id]
        if all(item.status == WorkStatus.COMPLETED for item in items):
            mission.status = WorkStatus.COMPLETED
        elif any(item.status == WorkStatus.IN_PROGRESS for item in items):
            mission.status = WorkStatus.IN_PROGRESS
        elif any(item.status == WorkStatus.REVIEW for item in items):
            mission.status = WorkStatus.REVIEW
        else:
            mission.status = WorkStatus.READY

    def status(self) -> CompanyStatus:
        active = [item for item in self.work_items.values() if item.status in {WorkStatus.READY, WorkStatus.IN_PROGRESS, WorkStatus.REVIEW}]
        return CompanyStatus(
            agents=len(self.agents),
            active_missions=sum(mission.status != WorkStatus.COMPLETED for mission in self.missions.values()),
            active_work_items=len(active),
            blocked_work_items=sum(item.status == WorkStatus.BLOCKED for item in self.work_items.values()),
        )


company_service = CompanyService()
