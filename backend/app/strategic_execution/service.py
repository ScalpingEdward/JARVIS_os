from collections import defaultdict, deque
from math import prod
from uuid import UUID

from .models import (
    AuditRecord,
    BottleneckRecord,
    CapacityForecastPoint,
    ExecutiveRecommendation,
    ExecutionAnalysisCreate,
    ExecutionAnalysisRecord,
    ExecutionRisk,
    ReadinessState,
    RecommendationSeverity,
    ScheduledTask,
    StrategicExecutionStatus,
)


_RISK_RANK = {
    ExecutionRisk.LOW: 1,
    ExecutionRisk.MEDIUM: 2,
    ExecutionRisk.HIGH: 3,
    ExecutionRisk.CRITICAL: 4,
}


class StrategicExecutionService:
    def __init__(self) -> None:
        self.analyses: dict[UUID, ExecutionAnalysisRecord] = {}
        self.audit_records: list[AuditRecord] = []

    def reset(self) -> None:
        self.analyses.clear()
        self.audit_records.clear()

    def create_analysis(self, payload: ExecutionAnalysisCreate) -> ExecutionAnalysisRecord:
        if any(item.workspace_id == payload.workspace_id and item.key == payload.key for item in self.analyses.values()):
            raise ValueError("execution analysis key already exists in workspace")

        task_map = {task.key: task for task in payload.tasks}
        order = self._topological_order(task_map)
        predecessors: dict[str, list[str]] = {key: list(task_map[key].dependencies) for key in task_map}
        successors: dict[str, list[str]] = defaultdict(list)
        for task in payload.tasks:
            for dependency in task.dependencies:
                successors[dependency].append(task.key)

        earliest_start: dict[str, int] = {}
        earliest_finish: dict[str, int] = {}
        for key in order:
            task = task_map[key]
            dependency_finish = max((earliest_finish[item] for item in predecessors[key]), default=0)
            earliest_start[key] = max(task.earliest_start_offset_minutes, dependency_finish)
            earliest_finish[key] = earliest_start[key] + task.duration_minutes

        total_duration = max(earliest_finish.values(), default=0)
        latest_finish: dict[str, int] = {}
        latest_start: dict[str, int] = {}
        for key in reversed(order):
            task = task_map[key]
            latest_finish[key] = min((latest_start[item] for item in successors[key]), default=total_duration)
            latest_start[key] = latest_finish[key] - task.duration_minutes

        bottlenecks, forecast, task_blockers = self._capacity_analysis(payload, earliest_start, earliest_finish)
        critical_path = [key for key in order if latest_start[key] - earliest_start[key] == 0]
        scheduled: list[ScheduledTask] = []
        for key in order:
            blockers = task_blockers.get(key, [])
            readiness = ReadinessState.BLOCKED if blockers else (
                ReadinessState.CONDITIONAL if task_map[key].human_approval_gate else ReadinessState.READY
            )
            scheduled.append(
                ScheduledTask(
                    task_key=key,
                    start_offset_minutes=earliest_start[key],
                    end_offset_minutes=earliest_finish[key],
                    slack_minutes=max(0, latest_start[key] - earliest_start[key]),
                    critical=key in critical_path,
                    readiness=readiness,
                    blocking_reasons=blockers,
                )
            )

        blocked = sum(item.readiness == ReadinessState.BLOCKED for item in scheduled)
        conditional = sum(item.readiness == ReadinessState.CONDITIONAL for item in scheduled)
        task_count = max(1, len(scheduled))
        readiness_score = max(0.0, 1.0 - blocked / task_count - (conditional / task_count) * 0.25)
        readiness_state = (
            ReadinessState.BLOCKED if blocked else ReadinessState.CONDITIONAL if conditional else ReadinessState.READY
        )
        success_probability = self._success_probability(payload, bottlenecks)
        execution_risk = self._execution_risk(payload, bottlenecks, readiness_state)
        recommendations = self._recommendations(payload, bottlenecks, scheduled, total_duration)
        decision_delta = self._decision_delta(payload, total_duration, readiness_score, success_probability)

        record = ExecutionAnalysisRecord(
            workspace_id=payload.workspace_id,
            owner_id=payload.owner_id,
            key=payload.key,
            title=payload.title,
            plan_id=payload.plan_id,
            portfolio_id=payload.portfolio_id,
            baseline_version=payload.baseline_version,
            scheduled_tasks=scheduled,
            critical_path=critical_path,
            total_duration_minutes=total_duration,
            readiness_score=round(readiness_score, 4),
            readiness_state=readiness_state,
            success_probability=round(success_probability, 4),
            execution_risk=execution_risk,
            bottlenecks=bottlenecks,
            capacity_forecast=forecast,
            recommendations=recommendations,
            decision_delta=decision_delta,
        )
        self.analyses[record.id] = record
        self._audit(record.workspace_id, record.owner_id, "execution.analysis-created", record.id, {"key": record.key})
        return record

    def list_analyses(self, workspace_id: str) -> list[ExecutionAnalysisRecord]:
        return sorted(
            [item for item in self.analyses.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def get_analysis(self, workspace_id: str, analysis_id: UUID) -> ExecutionAnalysisRecord | None:
        record = self.analyses.get(analysis_id)
        return record if record and record.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> StrategicExecutionStatus:
        items = [item for item in self.analyses.values() if item.workspace_id == workspace_id]
        return StrategicExecutionStatus(
            analyses=len(items),
            ready_analyses=sum(item.readiness_state == ReadinessState.READY for item in items),
            blocked_analyses=sum(item.readiness_state == ReadinessState.BLOCKED for item in items),
            open_bottlenecks=sum(len(item.bottlenecks) for item in items),
        )

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self.audit_records if item.workspace_id == workspace_id]

    @staticmethod
    def _topological_order(task_map: dict[str, object]) -> list[str]:
        indegree = {key: 0 for key in task_map}
        successors: dict[str, list[str]] = defaultdict(list)
        for key, task in task_map.items():
            for dependency in task.dependencies:
                indegree[key] += 1
                successors[dependency].append(key)
        queue = deque(sorted(key for key, value in indegree.items() if value == 0))
        order: list[str] = []
        while queue:
            key = queue.popleft()
            order.append(key)
            for successor in sorted(successors[key]):
                indegree[successor] -= 1
                if indegree[successor] == 0:
                    queue.append(successor)
        if len(order) != len(task_map):
            raise ValueError("execution task graph contains a cycle")
        return order

    @staticmethod
    def _capacity_analysis(payload, earliest_start, earliest_finish):
        windows_by_capability: dict[str, list[object]] = defaultdict(list)
        for window in payload.capacity_windows:
            windows_by_capability[window.capability].append(window)
        task_blockers: dict[str, list[str]] = defaultdict(list)
        forecast: list[CapacityForecastPoint] = []
        bottleneck_map: dict[str, dict] = {}
        checkpoints = sorted({0, *earliest_start.values(), *earliest_finish.values()})
        for capability in sorted({key for task in payload.tasks for key in task.required_capabilities}):
            affected: set[str] = set()
            max_required = 0.0
            minimum_available = float("inf")
            for offset in checkpoints:
                active = [
                    task for task in payload.tasks
                    if earliest_start[task.key] <= offset < earliest_finish[task.key]
                ]
                required = sum(task.required_capabilities.get(capability, 0.0) for task in active)
                available = max(
                    (
                        window.available_units for window in windows_by_capability.get(capability, [])
                        if window.window_start_offset_minutes <= offset < window.window_end_offset_minutes
                    ),
                    default=0.0,
                )
                if required > 0:
                    utilization = required / available if available > 0 else 1.0
                    forecast.append(
                        CapacityForecastPoint(
                            capability=capability,
                            offset_minutes=offset,
                            required_units=round(required, 4),
                            available_units=round(available, 4),
                            utilization=round(utilization, 4),
                        )
                    )
                if required > available:
                    max_required = max(max_required, required)
                    minimum_available = min(minimum_available, available)
                    for task in active:
                        if task.required_capabilities.get(capability, 0.0) > 0:
                            affected.add(task.key)
                            task_blockers[task.key].append(f"insufficient {capability} capacity")
            if affected:
                available = 0.0 if minimum_available == float("inf") else minimum_available
                bottleneck_map[capability] = {
                    "required": max_required,
                    "available": available,
                    "affected": sorted(affected),
                }
        bottlenecks = [
            BottleneckRecord(
                capability=capability,
                required_units=round(values["required"], 4),
                available_units=round(values["available"], 4),
                deficit_units=round(values["required"] - values["available"], 4),
                affected_task_keys=values["affected"],
                severity=RecommendationSeverity.CRITICAL if values["available"] == 0 else RecommendationSeverity.WARNING,
            )
            for capability, values in sorted(bottleneck_map.items())
        ]
        for key in task_blockers:
            task_blockers[key] = sorted(set(task_blockers[key]))
        return bottlenecks, forecast, task_blockers

    @staticmethod
    def _success_probability(payload, bottlenecks: list[BottleneckRecord]) -> float:
        base = prod(task.success_probability for task in payload.tasks) ** (1 / max(1, len(payload.tasks)))
        penalty = min(0.6, 0.12 * len(bottlenecks))
        return max(0.0, min(1.0, base - penalty))

    @staticmethod
    def _execution_risk(payload, bottlenecks, readiness_state):
        highest = max((_RISK_RANK[task.risk] for task in payload.tasks), default=1)
        if bottlenecks:
            highest = max(highest, 3 if all(item.severity != RecommendationSeverity.CRITICAL for item in bottlenecks) else 4)
        if readiness_state == ReadinessState.BLOCKED:
            highest = max(highest, 3)
        return next(level for level, rank in _RISK_RANK.items() if rank == highest)

    @staticmethod
    def _recommendations(payload, bottlenecks, scheduled, total_duration):
        recommendations: list[ExecutiveRecommendation] = []
        for bottleneck in bottlenecks:
            recommendations.append(
                ExecutiveRecommendation(
                    severity=bottleneck.severity,
                    action="increase-capacity-or-reschedule",
                    reason=f"Resolve {bottleneck.capability} capacity deficit before execution.",
                    task_keys=bottleneck.affected_task_keys,
                    metadata={"deficit_units": bottleneck.deficit_units},
                )
            )
        gates = [item.task_key for item in scheduled if item.readiness == ReadinessState.CONDITIONAL]
        if gates:
            recommendations.append(
                ExecutiveRecommendation(
                    severity=RecommendationSeverity.WARNING,
                    action="collect-human-approvals",
                    reason="Human approval gates remain before execution readiness.",
                    task_keys=gates,
                )
            )
        if payload.target_completion_minutes is not None and total_duration > payload.target_completion_minutes:
            recommendations.append(
                ExecutiveRecommendation(
                    severity=RecommendationSeverity.WARNING,
                    action="compress-critical-path",
                    reason="Forecast duration exceeds the target completion window.",
                    metadata={"forecast_minutes": total_duration, "target_minutes": payload.target_completion_minutes},
                )
            )
        if not recommendations:
            recommendations.append(
                ExecutiveRecommendation(
                    severity=RecommendationSeverity.INFO,
                    action="proceed-to-independent-review",
                    reason="No capacity or timing blocker was detected; execution remains advisory until approved.",
                )
            )
        return recommendations

    @staticmethod
    def _decision_delta(payload, total_duration, readiness_score, success_probability):
        baseline = payload.metadata.get("baseline", {}) if isinstance(payload.metadata, dict) else {}
        return {
            "duration_minutes_delta": total_duration - int(baseline.get("duration_minutes", total_duration)),
            "readiness_score_delta": round(readiness_score - float(baseline.get("readiness_score", readiness_score)), 4),
            "success_probability_delta": round(
                success_probability - float(baseline.get("success_probability", success_probability)), 4
            ),
        }

    def _audit(self, workspace_id: str, actor_id: str, action: str, target_id: UUID, details: dict) -> None:
        self.audit_records.append(
            AuditRecord(
                workspace_id=workspace_id,
                actor_id=actor_id,
                action=action,
                target_id=target_id,
                details=details,
            )
        )


strategic_execution_service = StrategicExecutionService()
