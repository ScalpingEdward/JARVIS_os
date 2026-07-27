from __future__ import annotations

from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.autonomous_task_planner import (
    TaskPlanAction,
    TaskPlanCreate,
    TaskPlanRecord,
    TaskPlanScores,
    TaskPlanState,
)


class AutonomousTaskPlannerService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], TaskPlanRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "autonomous-task-planner",
            "version": "21.114",
            "planning_enabled": True,
            "task_execution_enabled": False,
            "tool_execution_enabled": False,
            "agent_dispatch_enabled": False,
            "portfolio_mutation_enabled": False,
            "routing_mutation_enabled": False,
            "fund_movement_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: TaskPlanCreate) -> TaskPlanRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, flags = self._assess(payload)
        state = TaskPlanState.BLOCKED if "risk-brain-hard-block" in flags else TaskPlanState.PLANNED
        record = TaskPlanRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            goal=payload.goal,
            tasks=payload.tasks,
            scores=scores,
            risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[TaskPlanRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> TaskPlanRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, record_id: str, payload: TaskPlanAction) -> TaskPlanRecord:
        receipt = (payload.workspace_id, payload.operation_id)
        if receipt in self._operations:
            raise ValueError("operation replay detected")

        record = self.get(payload.workspace_id, record_id)
        transitions = {
            "submit-review": TaskPlanState.REVIEW_REQUIRED,
            "approve": TaskPlanState.APPROVED,
            "mark-ready": TaskPlanState.READY,
            "suspend": TaskPlanState.SUSPENDED,
            "revoke": TaskPlanState.REVOKED,
            "archive": TaskPlanState.ARCHIVED,
        }
        if payload.action not in transitions:
            raise ValueError("unsupported action")
        if payload.action == "approve" and record.risk_flags:
            raise ValueError("unresolved planner findings block approval")
        if payload.action == "mark-ready" and record.state != TaskPlanState.APPROVED:
            raise ValueError("human approval required before ready state")

        updated = record.model_copy(update={
            "state": transitions[payload.action],
            "approved_by": payload.actor if payload.action == "approve" else record.approved_by,
            "version": record.version + 1,
        })
        self._records[(payload.workspace_id, record_id)] = updated
        self._operations.add(receipt)
        self._audit_event(updated, payload.action, payload.actor, payload.operation_id, payload.reason)
        return updated

    def audit(self, workspace_id: str) -> List[dict]:
        return [entry for entry in self._audit if entry["workspace_id"] == workspace_id]

    def _assess(self, payload: TaskPlanCreate) -> tuple[TaskPlanScores, List[str]]:
        tasks = payload.tasks
        ids = {task.task_id for task in tasks}
        dependency_integrity = 1.0 if all(set(task.depends_on).issubset(ids) for task in tasks) else 0.0
        capability_coverage = mean(1.0 if task.required_capabilities else 0.7 for task in tasks)
        total_budget = sum(task.estimated_budget for task in tasks)
        budget_fit = 1.0 if total_budget <= payload.goal.max_total_budget else self._clamp(payload.goal.max_total_budget / max(total_budget, 1e-9))
        parallelism_fit = 1.0 if payload.goal.max_parallel_tasks <= max(1, len(tasks)) else 0.8
        plan_assurance = self._clamp(mean([dependency_integrity, capability_coverage, budget_fit, parallelism_fit]))
        residual_risk = self._clamp(1.0 - plan_assurance)

        flags: List[str] = []
        if total_budget > payload.goal.max_total_budget:
            flags.append("budget-breach")
        if any(task.execution_allowed for task in tasks):
            flags.append("execution-permission-present")
        if any(not task.required_capabilities for task in tasks):
            flags.append("capability-gap")
        if payload.goal.criticality >= 0.90 and (residual_risk >= 0.40 or any(task.execution_allowed for task in tasks)):
            flags.append("risk-brain-hard-block")

        scores = TaskPlanScores(
            dependency_integrity=self._clamp(dependency_integrity),
            capability_coverage=self._clamp(capability_coverage),
            budget_fit=self._clamp(budget_fit),
            parallelism_fit=self._clamp(parallelism_fit),
            plan_assurance=plan_assurance,
            residual_risk=residual_risk,
        )
        return scores, sorted(set(flags))

    def _audit_event(self, record: TaskPlanRecord, action: str, actor: str, operation_id: str, reason: str | None = None) -> None:
        self._audit.append({
            "audit_id": str(uuid4()),
            "workspace_id": record.workspace_id,
            "record_id": record.record_id,
            "action": action,
            "actor": actor,
            "operation_id": operation_id,
            "reason": reason,
            "version": record.version,
        })


autonomous_task_planner_service = AutonomousTaskPlannerService()
