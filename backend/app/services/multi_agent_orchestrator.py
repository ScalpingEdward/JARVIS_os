from __future__ import annotations

from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.multi_agent_orchestrator import (
    AgentBinding,
    OrchestrationCreate,
    OrchestrationRecord,
    OrchestrationScores,
    OrchestrationState,
    TaskAssignment,
)


class MultiAgentOrchestratorService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], OrchestrationRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "multi-agent-orchestrator-runtime",
            "version": "21.115",
            "assignment_runtime_enabled": True,
            "agent_dispatch_enabled": False,
            "tool_execution_enabled": False,
            "external_side_effects_enabled": False,
            "credential_mutation_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: OrchestrationCreate) -> OrchestrationRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._sources:
            raise ValueError("duplicate source_key for workspace")
        assignments, flags = self._bind(payload)
        scores = self._score(payload, assignments)
        if payload.criticality >= 0.90 and scores.residual_risk >= 0.60:
            flags.append("risk-brain-hard-block")
        state = OrchestrationState.BLOCKED if "risk-brain-hard-block" in flags else OrchestrationState.READY
        record = OrchestrationRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id,
            source_key=payload.source_key, planner_record_id=payload.planner_record_id,
            goal=payload.goal, state=state, assignments=assignments,
            scores=scores, risk_flags=sorted(set(flags)),
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._sources.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[OrchestrationRecord]:
        return [r for (ws, _), r in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> OrchestrationRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str,
            operation_id: str, task_id: str | None = None, reason: str | None = None) -> OrchestrationRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)

        if action == "submit-review":
            record = self._replace(record, state=OrchestrationState.REVIEW_REQUIRED)
        elif action == "approve":
            blocking = [f for f in record.risk_flags if f.startswith("unassigned") or f == "risk-brain-hard-block"]
            if blocking:
                raise ValueError("unresolved orchestration findings block approval")
            record = self._replace(record, state=OrchestrationState.APPROVED, approved_by=actor)
        elif action == "prepare-dispatch":
            if record.state != OrchestrationState.APPROVED:
                raise ValueError("human approval required before dispatch preparation")
            record = self._replace(record, state=OrchestrationState.DISPATCH_READY)
        elif action in {"mark-running", "mark-waiting", "require-handoff", "require-validation", "complete-task"}:
            if not task_id:
                raise ValueError("task_id required")
            if record.state not in {
                OrchestrationState.APPROVED, OrchestrationState.DISPATCH_READY,
                OrchestrationState.RUNNING, OrchestrationState.WAITING,
                OrchestrationState.HANDOFF_REQUIRED, OrchestrationState.VALIDATION_REQUIRED,
            }:
                raise ValueError("orchestration is not in an active governed state")
            record = self._task_transition(record, action, task_id)
        elif action == "suspend":
            record = self._replace(record, state=OrchestrationState.SUSPENDED)
        elif action == "cancel":
            record = self._replace(record, state=OrchestrationState.CANCELLED)
        elif action == "archive":
            record = self._replace(record, state=OrchestrationState.ARCHIVED)
        else:
            raise ValueError("unsupported action")

        self._records[(workspace_id, record_id)] = record
        self._operations.add(receipt)
        self._audit_event(record, action, actor, operation_id, {"task_id": task_id, "reason": reason})
        return record

    def audit(self, workspace_id: str) -> List[dict]:
        return [x for x in self._audit if x["workspace_id"] == workspace_id]

    def _bind(self, payload: OrchestrationCreate) -> tuple[List[TaskAssignment], List[str]]:
        assignments: List[TaskAssignment] = []
        flags: List[str] = []
        active_agents = [a for a in payload.agents if a.active and a.confidence >= payload.min_agent_confidence]
        for task in payload.tasks:
            candidates = [a for a in active_agents if self._eligible(a, task.required_capabilities, task.required_tools, task.required_data_domains)]
            chosen = max(candidates, key=lambda a: a.confidence, default=None)
            blockers: List[str] = []
            if not chosen:
                blockers.append("no-eligible-agent")
                flags.append(f"unassigned:{task.task_id}")
                readiness = 0.0
            else:
                readiness = chosen.confidence
            assignments.append(TaskAssignment(
                task_id=task.task_id, agent_id=chosen.agent_id if chosen else None,
                eligible=chosen is not None, readiness_score=self._clamp(readiness), blockers=blockers,
            ))
        return assignments, flags

    @staticmethod
    def _eligible(agent: AgentBinding, capabilities: List[str], tools: List[str], domains: List[str]) -> bool:
        return (
            set(capabilities).issubset(set(agent.capabilities)) and
            set(tools).issubset(set(agent.tools)) and
            set(domains).issubset(set(agent.data_domains))
        )

    def _score(self, payload: OrchestrationCreate, assignments: List[TaskAssignment]) -> OrchestrationScores:
        coverage = mean([1.0 if a.eligible else 0.0 for a in assignments])
        capability = mean([a.readiness_score for a in assignments])
        dependency_ready = 1.0
        validator_coverage = mean([1.0 if t.validator_required else 0.9 for t in payload.tasks])
        risk = self._clamp((1 - coverage) * 0.45 + (1 - capability) * 0.30 + (1 - validator_coverage) * 0.15 + max(0, len(payload.tasks) - 20) / 100)
        assurance = self._clamp(mean([coverage, capability, dependency_ready, validator_coverage]))
        return OrchestrationScores(
            assignment_coverage=self._clamp(coverage), dependency_readiness=dependency_ready,
            capability_coverage=self._clamp(capability), validation_coverage=self._clamp(validator_coverage),
            aggregate_assurance=assurance, residual_risk=risk,
        )

    def _task_transition(self, record: OrchestrationRecord, action: str, task_id: str) -> OrchestrationRecord:
        assignments = [a.model_copy(deep=True) for a in record.assignments]
        target = next((a for a in assignments if a.task_id == task_id), None)
        if not target:
            raise ValueError("unknown task_id")
        if not target.eligible:
            raise ValueError("task has no eligible agent")
        state_map = {
            "mark-running": ("running", OrchestrationState.RUNNING),
            "mark-waiting": ("waiting", OrchestrationState.WAITING),
            "require-handoff": ("handoff-required", OrchestrationState.HANDOFF_REQUIRED),
            "require-validation": ("validation-required", OrchestrationState.VALIDATION_REQUIRED),
            "complete-task": ("completed", OrchestrationState.RUNNING),
        }
        task_status, orchestration_state = state_map[action]
        target.status = task_status
        if action == "mark-running":
            target.attempts += 1
        if action == "require-validation":
            target.validator_status = "required"
        if action == "complete-task":
            target.validator_status = "passed"
            if all(a.status == "completed" for a in assignments):
                orchestration_state = OrchestrationState.COMPLETED
        return record.model_copy(update={"assignments": assignments, "state": orchestration_state, "version": record.version + 1})

    @staticmethod
    def _replace(record: OrchestrationRecord, **updates) -> OrchestrationRecord:
        updates["version"] = record.version + 1
        return record.model_copy(update=updates)

    def _audit_event(self, record: OrchestrationRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append({
            "audit_id": str(uuid4()), "workspace_id": record.workspace_id,
            "record_id": record.record_id, "action": action, "actor": actor,
            "operation_id": operation_id, "metadata": metadata or {},
        })


multi_agent_orchestrator_service = MultiAgentOrchestratorService()
