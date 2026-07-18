from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    AgentAssignment,
    ApprovalDecision,
    ApprovalRequest,
    AuditRecord,
    MissionPriority,
    MissionScore,
    OrchestrationAnalysis,
    OrchestrationCreate,
    OrchestrationRecord,
    OrchestrationStatus,
    OrchestrationStatusResponse,
    ResourceConflict,
    ScheduledTask,
)


_PRIORITY_WEIGHT = {
    MissionPriority.low: 10.0,
    MissionPriority.medium: 35.0,
    MissionPriority.high: 65.0,
    MissionPriority.critical: 90.0,
}


class ExecutiveMissionOrchestrationService:
    def __init__(self) -> None:
        self._records: dict[UUID, OrchestrationRecord] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _write_audit(self, workspace_id: str, action: str, actor_id: str, orchestration_id: UUID | None = None, details: dict | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, action=action, actor_id=actor_id, orchestration_id=orchestration_id, details=details or {}, created_at=self._now()))

    def create(self, payload: OrchestrationCreate) -> OrchestrationRecord:
        now = self._now()
        record = OrchestrationRecord(**payload.model_dump(), created_at=now, updated_at=now)
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.title == payload.title for item in self._records.values()):
                raise ValueError("An orchestration with this title already exists in the workspace")
            self._records[record.id] = record
            self._write_audit(payload.workspace_id, "orchestration-created", payload.owner_id, record.id, {"missions": len(payload.missions), "agents": len(payload.agents)})
        return record

    def list_records(self, workspace_id: str) -> list[OrchestrationRecord]:
        with self._lock:
            return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, orchestration_id: UUID, workspace_id: str) -> OrchestrationRecord | None:
        with self._lock:
            record = self._records.get(orchestration_id)
            return record if record is not None and record.workspace_id == workspace_id else None

    @staticmethod
    def _mission_score(mission, agents) -> MissionScore:
        required = {cap for task in mission.tasks for cap in task.required_capabilities}
        available = {cap for agent in agents for cap in agent.capabilities if agent.available_hours > 0}
        readiness = 100.0 if not required else 100.0 * len(required & available) / len(required)
        risk_penalty = mission.risk * 0.25
        score = _PRIORITY_WEIGHT[mission.priority] * 0.3 + mission.strategic_value * 0.3 + mission.urgency * 0.25 + readiness * 0.25 - risk_penalty
        return MissionScore(mission_key=mission.key, priority_score=round(max(0.0, min(100.0, score)), 2), strategic_value=mission.strategic_value, urgency=mission.urgency, risk_penalty=round(risk_penalty, 2), readiness_score=round(readiness, 2), explanation=[f"Priority tier contribution: {_PRIORITY_WEIGHT[mission.priority]:.1f}", f"Strategic value: {mission.strategic_value:.1f}", f"Urgency: {mission.urgency:.1f}", f"Capability readiness: {readiness:.1f}%", f"Risk penalty: {risk_penalty:.1f}"])

    @staticmethod
    def _topological_order(tasks) -> list[str]:
        indegree = {task.key: 0 for task in tasks}
        edges: dict[str, list[str]] = defaultdict(list)
        for task in tasks:
            for dependency in task.dependency_keys:
                edges[dependency].append(task.key)
                indegree[task.key] += 1
        queue = deque(sorted(key for key, degree in indegree.items() if degree == 0))
        ordered: list[str] = []
        while queue:
            key = queue.popleft()
            ordered.append(key)
            for dependent in sorted(edges[key]):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    queue.append(dependent)
        if len(ordered) != len(tasks):
            raise ValueError("Mission task graph contains a cycle")
        return ordered

    @staticmethod
    def _choose_agent(task, agents, remaining_hours: dict[str, float]) -> AgentAssignment:
        eligible = []
        required = set(task.required_capabilities)
        candidates = set(task.candidate_agent_ids)
        for agent in agents:
            if candidates and agent.agent_id not in candidates:
                continue
            capability_fit = 1.0 if not required else len(required & set(agent.capabilities)) / len(required)
            remaining = remaining_hours.get(agent.agent_id, 0.0)
            capacity_fit = min(1.0, remaining / task.duration_hours)
            fit = capability_fit * 0.55 + capacity_fit * 0.25 + agent.reliability * 0.2
            eligible.append((fit, remaining, agent.agent_id, capability_fit))
        if not eligible:
            return AgentAssignment(mission_key="", task_key=task.key, assigned_agent_id=None, fit_score=0, explanation=["No candidate agent matched the task constraints"])
        fit, remaining, agent_id, capability_fit = max(eligible)
        if capability_fit < 1.0 or remaining < task.duration_hours:
            return AgentAssignment(mission_key="", task_key=task.key, assigned_agent_id=None, fit_score=round(fit * 100, 2), explanation=["No agent has both full capability fit and sufficient remaining capacity"])
        remaining_hours[agent_id] -= task.duration_hours
        return AgentAssignment(mission_key="", task_key=task.key, assigned_agent_id=agent_id, fit_score=round(fit * 100, 2), explanation=["Agent has all required capabilities", f"Remaining capacity before assignment: {remaining:.1f}h"])

    def analyze(self, orchestration_id: UUID, workspace_id: str, actor_id: str) -> OrchestrationRecord:
        with self._lock:
            record = self._records.get(orchestration_id)
            if record is None or record.workspace_id != workspace_id:
                raise KeyError("Orchestration not found")
            ranked = sorted((self._mission_score(mission, record.agents) for mission in record.missions), key=lambda item: (-item.priority_score, item.mission_key))
            mission_map = {mission.key: mission for mission in record.missions}
            remaining_hours = {agent.agent_id: max(0.0, agent.available_hours - agent.current_load_hours) for agent in record.agents}
            initial_hours = dict(remaining_hours)
            schedule: list[ScheduledTask] = []
            assignments: list[AgentAssignment] = []
            deferred: list[str] = []
            end_times: dict[str, float] = {}
            active_windows: list[tuple[float, float]] = []
            sequence = 1
            for score in ranked:
                mission = mission_map[score.mission_key]
                task_map = {task.key: task for task in mission.tasks}
                for task_key in self._topological_order(mission.tasks):
                    task = task_map[task_key]
                    assignment = self._choose_agent(task, record.agents, remaining_hours).model_copy(update={"mission_key": mission.key})
                    assignments.append(assignment)
                    ref = f"{mission.key}:{task.key}"
                    blocked = []
                    if assignment.assigned_agent_id is None:
                        blocked.append("No eligible agent capacity")
                    dependency_end = max((end_times.get(f"{mission.key}:{dependency}", 0.0) for dependency in task.dependency_keys), default=0.0)
                    start = dependency_end
                    while sum(1 for window_start, window_end in active_windows if window_start <= start < window_end) >= record.max_parallel_tasks:
                        start = min(window_end for window_start, window_end in active_windows if window_start <= start < window_end)
                    end = start + task.duration_hours
                    if end > record.planning_horizon_hours:
                        blocked.append("Task exceeds planning horizon")
                    if blocked:
                        deferred.append(ref)
                    else:
                        active_windows.append((start, end))
                        end_times[ref] = end
                    schedule.append(ScheduledTask(mission_key=mission.key, task_key=task.key, sequence=sequence, start_hour=round(start, 2), end_hour=round(end, 2), dependency_keys=task.dependency_keys, assigned_agent_id=assignment.assigned_agent_id, blocked_reasons=blocked, requires_human_approval=task.requires_human_approval))
                    sequence += 1
            conflicts: list[ResourceConflict] = []
            by_agent: dict[str, list[str]] = defaultdict(list)
            for assignment in assignments:
                if assignment.assigned_agent_id:
                    by_agent[assignment.assigned_agent_id].append(f"{assignment.mission_key}:{assignment.task_key}")
            for agent_id, refs in by_agent.items():
                capacity = initial_hours.get(agent_id, 0.0)
                used = capacity - remaining_hours.get(agent_id, 0.0)
                if capacity > 0 and used / capacity >= 0.9:
                    conflicts.append(ResourceConflict(resource_key=f"agent:{agent_id}", task_references=refs, severity="high" if used > capacity else "warning", explanation=f"Agent utilization is {used / capacity * 100:.1f}%"))
            utilization = {agent_id: round(((initial - remaining_hours.get(agent_id, 0.0)) / initial * 100) if initial else 0.0, 2) for agent_id, initial in initial_hours.items()}
            duration = max((item.end_hour for item in schedule if not item.blocked_reasons), default=0.0)
            recommendations = []
            if deferred:
                recommendations.append("Resolve capability or capacity gaps before mission release")
            if conflicts:
                recommendations.append("Rebalance highly utilized agents or extend the planning window")
            if not recommendations:
                recommendations.append("Portfolio is schedulable; retain human approval before execution handoff")
            analysis = OrchestrationAnalysis(analyzed_at=self._now(), ranked_missions=ranked, task_schedule=schedule, assignments=assignments, conflicts=conflicts, projected_duration_hours=round(duration, 2), horizon_fit=duration <= record.planning_horizon_hours and not deferred, utilization_by_agent=utilization, deferred_tasks=deferred, recommendations=recommendations)
            updated = record.model_copy(update={"analysis": analysis, "status": OrchestrationStatus.pending_approval, "updated_at": self._now()})
            self._records[orchestration_id] = updated
            self._write_audit(workspace_id, "orchestration-analyzed", actor_id, orchestration_id, {"deferred_tasks": len(deferred), "conflicts": len(conflicts)})
            return updated

    def approve(self, orchestration_id: UUID, payload: ApprovalRequest) -> OrchestrationRecord:
        with self._lock:
            record = self._records.get(orchestration_id)
            if record is None or record.workspace_id != payload.workspace_id:
                raise KeyError("Orchestration not found")
            if record.analysis is None:
                raise ValueError("Orchestration must be analyzed before approval")
            if payload.reviewer_id == record.owner_id:
                raise ValueError("Orchestration owners cannot approve their own orchestration")
            next_status = OrchestrationStatus.approved if payload.decision == ApprovalDecision.approve else OrchestrationStatus.rejected
            updated = record.model_copy(update={"status": next_status, "approved_by": payload.reviewer_id, "approval_reason": payload.reason, "updated_at": self._now()})
            self._records[orchestration_id] = updated
            self._write_audit(payload.workspace_id, f"orchestration-{payload.decision.value}d", payload.reviewer_id, orchestration_id, {"reason": payload.reason})
            return updated

    def status(self, workspace_id: str) -> OrchestrationStatusResponse:
        records = self.list_records(workspace_id)
        return OrchestrationStatusResponse(orchestrations=len(records), pending_approval=sum(item.status == OrchestrationStatus.pending_approval for item in records), approved=sum(item.status == OrchestrationStatus.approved for item in records), rejected=sum(item.status == OrchestrationStatus.rejected for item in records), conflicts=sum(len(item.analysis.conflicts) for item in records if item.analysis))

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


executive_mission_orchestration_service = ExecutiveMissionOrchestrationService()
