from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
from secrets import token_urlsafe

from .models import (
    AuditEvent,
    ExecutionCommand,
    ExecutionPlanAction,
    ExecutionPlanCreate,
    ExecutionPlanRecord,
    ExecutionPlanState,
    WorkPackagePlan,
)


class ExecutionPlanError(RuntimeError):
    pass


class ExecutiveExecutionPlannerService:
    """In-memory governed planner. Persistence can replace the stores without changing policy."""

    def __init__(self) -> None:
        self._records: dict[str, ExecutionPlanRecord] = {}
        self._source_index: dict[tuple[str, str], str] = {}
        self._audit: list[AuditEvent] = []
        self._used_approval_tokens: set[str] = set()
        self._used_receipts: set[str] = set()

    def status(self) -> dict[str, object]:
        return {
            "module": "executive-execution-planner",
            "version": "21.09",
            "status": "operational",
            "records": len(self._records),
            "safety_boundary": "planning-only",
        }

    def create(self, payload: ExecutionPlanCreate, actor: str = "system") -> ExecutionPlanRecord:
        duplicate = self._source_index.get((payload.workspace_id, payload.source_key))
        if duplicate:
            raise ExecutionPlanError(f"duplicate source_key; existing record={duplicate}")

        if payload.risk_brain_hard_block:
            state = ExecutionPlanState.BLOCKED
            notes = ["Risk Brain hard block is authoritative."]
        elif not payload.investment_decision_approved or not payload.v21_08_evidence:
            state = ExecutionPlanState.EVIDENCE_REQUIRED
            notes = ["Approved v21.08 decision and evidence are mandatory."]
        elif any(not item.dependency_ready for item in payload.work_packages):
            state = ExecutionPlanState.BLOCKED
            notes = ["Dependency-blocked work packages cannot enter execution planning."]
        else:
            state = ExecutionPlanState.PLANNING
            notes = []

        record = ExecutionPlanRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            investment_decision_id=payload.investment_decision_id,
            state=state,
            decision_notes=notes,
        )
        self._records[record.id] = record
        self._source_index[(record.workspace_id, record.source_key)] = record.id
        self._append_audit(record, actor, "create", None, record.state.value)
        if state == ExecutionPlanState.PLANNING:
            self._generate(record, payload, actor)
        return record

    def list(self, workspace_id: str) -> list[ExecutionPlanRecord]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> ExecutionPlanRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise ExecutionPlanError("record not found")
        return record

    def execute(self, workspace_id: str, record_id: str, action: ExecutionPlanAction) -> ExecutionPlanRecord:
        record = self.get(workspace_id, record_id)
        before = record.state.value

        if action.command == ExecutionCommand.GENERATE:
            raise ExecutionPlanError("generation occurs during governed intake")
        if action.command == ExecutionCommand.APPROVE:
            if record.state not in {
                ExecutionPlanState.EXECUTION_PLAN_READY,
                ExecutionPlanState.HUMAN_REVIEW_REQUIRED,
            }:
                raise ExecutionPlanError("record is not approvable")
            token = action.approval_token or token_urlsafe(24)
            if token in self._used_approval_tokens:
                raise ExecutionPlanError("approval token replay detected")
            self._used_approval_tokens.add(token)
            record.approval_token = token
            record.state = ExecutionPlanState.APPROVED
        elif action.command == ExecutionCommand.ISSUE:
            if record.state != ExecutionPlanState.APPROVED:
                raise ExecutionPlanError("only approved plans can be issued")
            if not action.downstream_receipt:
                raise ExecutionPlanError("downstream receipt is required")
            if action.downstream_receipt in self._used_receipts:
                raise ExecutionPlanError("downstream receipt replay detected")
            self._used_receipts.add(action.downstream_receipt)
            record.downstream_receipt = action.downstream_receipt
            record.state = ExecutionPlanState.ISSUED_TO_ORCHESTRATOR
        elif action.command == ExecutionCommand.REJECT:
            if record.state in {ExecutionPlanState.ISSUED_TO_ORCHESTRATOR, ExecutionPlanState.ARCHIVED}:
                raise ExecutionPlanError("terminal record cannot be rejected")
            record.state = ExecutionPlanState.REJECTED
            if action.reason:
                record.decision_notes.append(action.reason)
        elif action.command == ExecutionCommand.ARCHIVE:
            record.state = ExecutionPlanState.ARCHIVED

        record.updated_at = datetime.utcnow()
        self._append_audit(record, action.actor, action.command.value, before, record.state.value)
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def _generate(self, record: ExecutionPlanRecord, payload: ExecutionPlanCreate, actor: str) -> None:
        before = record.state.value
        ordered = self._topological_order(payload)
        by_key = {item.key: item for item in payload.work_packages}
        end_by_key: dict[str, int] = {}
        lane_end = [0] * payload.max_parallel_workstreams
        plans: list[WorkPackagePlan] = []

        for sequence, key in enumerate(ordered, start=1):
            item = by_key[key]
            dependency_end = max((end_by_key[d] for d in item.dependencies), default=0)
            lane = min(range(len(lane_end)), key=lambda idx: max(lane_end[idx], dependency_end))
            start_day = max(lane_end[lane], dependency_end)
            end_day = start_day + item.duration_days
            lane_end[lane] = end_day
            end_by_key[key] = end_day
            plans.append(
                WorkPackagePlan(
                    key=item.key,
                    title=item.title,
                    owner=item.owner,
                    sequence=sequence,
                    lane=lane + 1,
                    start_day=start_day,
                    end_day=end_day,
                    effort_points=item.effort_points,
                    duration_days=item.duration_days,
                    expected_value=item.expected_value,
                    allocated_budget=item.allocated_budget,
                    dependencies=item.dependencies,
                    deliverables=item.deliverables,
                    exit_criteria=item.exit_criteria,
                    rollback_plan=item.rollback_plan,
                )
            )

        critical_path = self._critical_path(ordered, by_key)
        critical_set = set(critical_path)
        for plan in plans:
            plan.is_critical_path = plan.key in critical_set

        total_effort = sum(p.effort_points for p in plans)
        horizon = max((p.end_day for p in plans), default=0)
        capacity_ratio = total_effort / payload.available_capacity_points
        readiness = 100.0
        bottlenecks: list[str] = []
        if capacity_ratio > 1:
            readiness -= min(45.0, (capacity_ratio - 1) * 55)
            bottlenecks.append("available capacity is below planned effort")
        if horizon > payload.planning_horizon_days:
            readiness -= min(35.0, ((horizon / payload.planning_horizon_days) - 1) * 45)
            bottlenecks.append("critical schedule exceeds planning horizon")
        missing_exit = [p.key for p in plans if not p.exit_criteria]
        if missing_exit:
            readiness -= min(20.0, len(missing_exit) * 5)
            bottlenecks.append("work packages without exit criteria: " + ", ".join(missing_exit))

        dependency_density = sum(len(p.dependencies) for p in plans) / max(1, len(plans))
        confidence = max(0.0, min(100.0, readiness - dependency_density * 3 + min(10, len(payload.strategic_constraints))))

        record.work_packages = plans
        record.critical_path = critical_path
        record.bottlenecks = bottlenecks
        record.total_effort_points = total_effort
        record.total_budget = round(sum(p.allocated_budget for p in plans), 2)
        record.total_expected_value = round(sum(p.expected_value for p in plans), 2)
        record.execution_readiness_score = round(max(0.0, readiness), 2)
        record.delivery_confidence_score = round(confidence, 2)
        if bottlenecks or readiness < 75 or confidence < 70:
            record.state = ExecutionPlanState.HUMAN_REVIEW_REQUIRED
        else:
            record.state = ExecutionPlanState.EXECUTION_PLAN_READY
        record.updated_at = datetime.utcnow()
        self._append_audit(
            record,
            actor,
            "generate",
            before,
            record.state.value,
            {"critical_path": critical_path, "bottlenecks": bottlenecks},
        )

    @staticmethod
    def _topological_order(payload: ExecutionPlanCreate) -> list[str]:
        indegree = {item.key: 0 for item in payload.work_packages}
        graph: dict[str, list[str]] = defaultdict(list)
        for item in payload.work_packages:
            for dependency in item.dependencies:
                graph[dependency].append(item.key)
                indegree[item.key] += 1
        queue = deque(sorted(key for key, degree in indegree.items() if degree == 0))
        result: list[str] = []
        while queue:
            key = queue.popleft()
            result.append(key)
            for child in sorted(graph[key]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
        if len(result) != len(indegree):
            raise ExecutionPlanError("cyclic dependency graph detected")
        return result

    @staticmethod
    def _critical_path(ordered: list[str], by_key: dict[str, object]) -> list[str]:
        distance: dict[str, int] = {}
        predecessor: dict[str, str | None] = {}
        for key in ordered:
            item = by_key[key]
            if not item.dependencies:
                distance[key] = item.duration_days
                predecessor[key] = None
            else:
                parent = max(item.dependencies, key=lambda dep: distance[dep])
                distance[key] = distance[parent] + item.duration_days
                predecessor[key] = parent
        if not distance:
            return []
        cursor: str | None = max(distance, key=distance.get)
        path: list[str] = []
        while cursor is not None:
            path.append(cursor)
            cursor = predecessor[cursor]
        return list(reversed(path))

    def _append_audit(
        self,
        record: ExecutionPlanRecord,
        actor: str,
        action: str,
        from_state: str | None,
        to_state: str,
        details: dict[str, object] | None = None,
    ) -> None:
        self._audit.append(
            AuditEvent(
                workspace_id=record.workspace_id,
                record_id=record.id,
                action=action,
                actor=actor,
                from_state=from_state,
                to_state=to_state,
                details=details or {},
            )
        )
