from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    AgentRecord,
    AgentRegistration,
    AgentState,
    AuditRecord,
    MissionAction,
    MissionControlStatus,
    MissionCreate,
    MissionRecord,
    MissionState,
    TaskRuntime,
    TaskState,
)


class MissionControlError(ValueError):
    pass


class MissionControlService:
    def __init__(self) -> None:
        self._agents: dict[UUID, AgentRecord] = {}
        self._missions: dict[UUID, MissionRecord] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    def reset(self) -> None:
        with self._lock:
            self._agents.clear()
            self._missions.clear()
            self._audit.clear()

    def status(self) -> MissionControlStatus:
        agents = list(self._agents.values())
        missions = list(self._missions.values())
        return MissionControlStatus(
            total_agents=len(agents),
            available_agents=sum(a.state == AgentState.AVAILABLE for a in agents),
            total_missions=len(missions),
            active_missions=sum(m.state in {MissionState.APPROVED, MissionState.RUNNING, MissionState.PAUSED} for m in missions),
        )

    def register_agent(self, payload: AgentRegistration) -> AgentRecord:
        with self._lock:
            if any(a.workspace_id == payload.workspace_id and a.agent_key == payload.agent_key for a in self._agents.values()):
                raise MissionControlError("agent key already exists in workspace")
            record = AgentRecord(**payload.model_dump(exclude={"human_approved"}))
            self._agents[record.id] = record
            self._record(payload.workspace_id, "agent.registered", payload.agent_key, record.id)
            return record

    def heartbeat(self, agent_id: UUID, workspace_id: str) -> AgentRecord:
        with self._lock:
            agent = self._require_agent(agent_id, workspace_id)
            agent.last_heartbeat_at = datetime.now(timezone.utc)
            if agent.state in {AgentState.OFFLINE, AgentState.DEGRADED}:
                agent.state = AgentState.AVAILABLE
            self._record(workspace_id, "agent.heartbeat", agent.agent_key, agent.id)
            return agent

    def list_agents(self, workspace_id: str) -> list[AgentRecord]:
        return [a for a in self._agents.values() if a.workspace_id == workspace_id]

    def create_mission(self, payload: MissionCreate) -> MissionRecord:
        with self._lock:
            if any(m.workspace_id == payload.workspace_id and m.mission_key == payload.mission_key for m in self._missions.values()):
                raise MissionControlError("mission key already exists in workspace")
            runtime = [TaskRuntime(task_key=task.key, state=TaskState.BLOCKED if task.depends_on else TaskState.READY) for task in payload.tasks]
            record = MissionRecord(**payload.model_dump(exclude={"human_approved"}), runtime=runtime)
            self._missions[record.id] = record
            self._record(payload.workspace_id, "mission.created", payload.owner_id, record.id)
            return record

    def list_missions(self, workspace_id: str) -> list[MissionRecord]:
        return [m for m in self._missions.values() if m.workspace_id == workspace_id]

    def get_mission(self, mission_id: UUID, workspace_id: str) -> MissionRecord:
        return self._require_mission(mission_id, workspace_id)

    def plan(self, mission_id: UUID, workspace_id: str, action: MissionAction) -> MissionRecord:
        return self._transition(mission_id, workspace_id, action, {MissionState.DRAFT}, MissionState.PLANNED, "mission.planned")

    def approve(self, mission_id: UUID, workspace_id: str, action: MissionAction) -> MissionRecord:
        mission = self._require_mission(mission_id, workspace_id)
        if action.actor_id == mission.owner_id:
            raise MissionControlError("mission owner cannot self-approve")
        mission = self._transition(mission_id, workspace_id, action, {MissionState.PLANNED}, MissionState.APPROVED, "mission.approved")
        mission.approved_by = action.actor_id
        return mission

    def start(self, mission_id: UUID, workspace_id: str, action: MissionAction) -> MissionRecord:
        mission = self._transition(mission_id, workspace_id, action, {MissionState.APPROVED, MissionState.PAUSED}, MissionState.RUNNING, "mission.started")
        self._assign_ready_tasks(mission)
        return mission

    def pause(self, mission_id: UUID, workspace_id: str, action: MissionAction) -> MissionRecord:
        return self._transition(mission_id, workspace_id, action, {MissionState.RUNNING}, MissionState.PAUSED, "mission.paused")

    def complete_task(self, mission_id: UUID, task_key: str, workspace_id: str, action: MissionAction) -> MissionRecord:
        with self._lock:
            mission = self._require_mission(mission_id, workspace_id)
            if mission.state != MissionState.RUNNING:
                raise MissionControlError("mission is not running")
            runtime = next((r for r in mission.runtime if r.task_key == task_key), None)
            if runtime is None:
                raise MissionControlError("task not found")
            if runtime.state not in {TaskState.ASSIGNED, TaskState.IN_PROGRESS, TaskState.WAITING_APPROVAL}:
                raise MissionControlError("task is not completable")
            definition = next(t for t in mission.tasks if t.key == task_key)
            if definition.requires_human_approval and not action.human_approved:
                raise MissionControlError("human approval is required")
            runtime.state = TaskState.COMPLETED
            if runtime.assigned_agent_id:
                agent = self._agents[runtime.assigned_agent_id]
                agent.active_task_ids = [x for x in agent.active_task_ids if x != mission.id]
                agent.state = AgentState.AVAILABLE if not agent.active_task_ids else AgentState.BUSY
            completed = {r.task_key for r in mission.runtime if r.state == TaskState.COMPLETED}
            for item, task in zip(mission.runtime, mission.tasks):
                if item.state == TaskState.BLOCKED and set(task.depends_on).issubset(completed):
                    item.state = TaskState.READY
            self._assign_ready_tasks(mission)
            if all(r.state == TaskState.COMPLETED for r in mission.runtime):
                mission.state = MissionState.COMPLETED
            mission.updated_at = datetime.now(timezone.utc)
            self._record(workspace_id, "task.completed", action.actor_id, mission.id, {"task_key": task_key})
            return mission

    def archive(self, mission_id: UUID, workspace_id: str, action: MissionAction) -> MissionRecord:
        return self._transition(mission_id, workspace_id, action, {MissionState.COMPLETED, MissionState.FAILED}, MissionState.ARCHIVED, "mission.archived")

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [a for a in self._audit if a.workspace_id == workspace_id]

    def _assign_ready_tasks(self, mission: MissionRecord) -> None:
        for runtime in mission.runtime:
            if runtime.state != TaskState.READY:
                continue
            definition = next(t for t in mission.tasks if t.key == runtime.task_key)
            candidates = [
                a for a in self._agents.values()
                if a.workspace_id == mission.workspace_id
                and a.state in {AgentState.AVAILABLE, AgentState.BUSY}
                and a.role == definition.required_role
                and set(definition.required_capabilities).issubset(set(a.capabilities))
                and len(a.active_task_ids) < a.max_concurrent_tasks
            ]
            if not candidates:
                continue
            agent = sorted(candidates, key=lambda a: (len(a.active_task_ids), a.agent_key))[0]
            runtime.assigned_agent_id = agent.id
            runtime.state = TaskState.WAITING_APPROVAL if definition.requires_human_approval else TaskState.ASSIGNED
            agent.active_task_ids.append(mission.id)
            agent.state = AgentState.BUSY

    def _transition(self, mission_id: UUID, workspace_id: str, action: MissionAction, allowed: set[MissionState], target: MissionState, audit_action: str) -> MissionRecord:
        with self._lock:
            mission = self._require_mission(mission_id, workspace_id)
            if mission.state not in allowed:
                raise MissionControlError(f"invalid transition from {mission.state}")
            mission.state = target
            mission.updated_at = datetime.now(timezone.utc)
            self._record(workspace_id, audit_action, action.actor_id, mission.id, {"reason": action.reason})
            return mission

    def _require_agent(self, agent_id: UUID, workspace_id: str) -> AgentRecord:
        agent = self._agents.get(agent_id)
        if agent is None or agent.workspace_id != workspace_id:
            raise MissionControlError("agent not found")
        return agent

    def _require_mission(self, mission_id: UUID, workspace_id: str) -> MissionRecord:
        mission = self._missions.get(mission_id)
        if mission is None or mission.workspace_id != workspace_id:
            raise MissionControlError("mission not found")
        return mission

    def _record(self, workspace_id: str, action: str, actor_id: str, entity_id: UUID, metadata: dict | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, action=action, actor_id=actor_id, entity_id=entity_id, metadata=metadata or {}))


mission_control_service = MissionControlService()
