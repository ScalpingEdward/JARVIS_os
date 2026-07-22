from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
from secrets import token_urlsafe

from .models import (
    AuditEvent,
    OrchestrationAction,
    OrchestrationCommand,
    OrchestrationCreate,
    OrchestrationRecord,
    OrchestrationState,
    StageRuntime,
)


class OrchestrationError(RuntimeError):
    pass


class AutonomousExecutiveOrchestratorService:
    """Governed orchestration coordinator with no direct external side effects."""

    def __init__(self) -> None:
        self._records: dict[str, OrchestrationRecord] = {}
        self._source_index: dict[tuple[str, str], str] = {}
        self._audit: list[AuditEvent] = []
        self._used_approval_tokens: set[str] = set()
        self._used_dispatch_tokens: set[str] = set()
        self._used_receipts: set[str] = set()

    def status(self) -> dict[str, object]:
        return {
            "module": "autonomous-executive-orchestrator",
            "version": "21.10",
            "status": "operational",
            "records": len(self._records),
            "safety_boundary": "coordination-only",
        }

    def create(self, payload: OrchestrationCreate, actor: str = "system") -> OrchestrationRecord:
        duplicate = self._source_index.get((payload.workspace_id, payload.source_key))
        if duplicate:
            raise OrchestrationError(f"duplicate source_key; existing record={duplicate}")

        if payload.risk_brain_hard_block:
            state = OrchestrationState.BLOCKED
            notes = ["Risk Brain hard block is authoritative."]
        elif not payload.execution_plan_approved or not payload.v21_09_evidence:
            state = OrchestrationState.EVIDENCE_REQUIRED
            notes = ["Approved v21.09 execution plan and evidence are mandatory."]
        elif any(not stage.dispatch_enabled for stage in payload.stages):
            state = OrchestrationState.HUMAN_REVIEW_REQUIRED
            notes = ["One or more stages are dispatch-disabled and require review."]
        else:
            state = OrchestrationState.INTAKE
            notes = []

        record = OrchestrationRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            execution_plan_id=payload.execution_plan_id,
            state=state,
            decision_notes=notes,
        )
        self._records[record.id] = record
        self._source_index[(record.workspace_id, record.source_key)] = record.id
        self._append_audit(record, actor, "create", None, state.value)

        if state in {OrchestrationState.INTAKE, OrchestrationState.HUMAN_REVIEW_REQUIRED}:
            self._prepare(record, payload, actor)
        return record

    def list(self, workspace_id: str) -> list[OrchestrationRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> OrchestrationRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise OrchestrationError("record not found")
        return record

    def execute(self, workspace_id: str, record_id: str, action: OrchestrationAction) -> OrchestrationRecord:
        record = self.get(workspace_id, record_id)
        before = record.state.value

        if action.command == OrchestrationCommand.APPROVE:
            if record.state not in {OrchestrationState.ORCHESTRATION_READY, OrchestrationState.HUMAN_REVIEW_REQUIRED}:
                raise OrchestrationError("record is not approvable")
            token = action.approval_token or token_urlsafe(24)
            if token in self._used_approval_tokens:
                raise OrchestrationError("approval token replay detected")
            self._used_approval_tokens.add(token)
            record.approval_token = token
            record.state = OrchestrationState.APPROVED

        elif action.command == OrchestrationCommand.DISPATCH:
            if record.state not in {OrchestrationState.APPROVED, OrchestrationState.DISPATCHING, OrchestrationState.MONITORING}:
                raise OrchestrationError("workflow is not dispatchable")
            stage = self._stage(record, action.stage_key)
            if stage.status != "ready":
                raise OrchestrationError("stage is not ready")
            token = action.dispatch_token or token_urlsafe(24)
            if token in self._used_dispatch_tokens:
                raise OrchestrationError("dispatch token replay detected")
            self._used_dispatch_tokens.add(token)
            stage.dispatch_token = token
            stage.status = "running"
            record.ready_queue = [key for key in record.ready_queue if key != stage.key]
            record.active_stages.append(stage.key)
            record.state = OrchestrationState.MONITORING

        elif action.command == OrchestrationCommand.COMPLETE_STAGE:
            stage = self._stage(record, action.stage_key)
            if stage.status != "running":
                raise OrchestrationError("stage is not running")
            if not action.result_receipt:
                raise OrchestrationError("result receipt is required")
            if action.result_receipt in self._used_receipts:
                raise OrchestrationError("result receipt replay detected")
            self._used_receipts.add(action.result_receipt)
            stage.result_receipt = action.result_receipt
            stage.status = "completed"
            record.active_stages = [key for key in record.active_stages if key != stage.key]
            record.completed_stages.append(stage.key)
            self._refresh_ready_queue(record)
            record.state = OrchestrationState.COMPLETED if len(record.completed_stages) == len(record.stages) else OrchestrationState.MONITORING

        elif action.command == OrchestrationCommand.FAIL_STAGE:
            stage = self._stage(record, action.stage_key)
            if stage.status != "running":
                raise OrchestrationError("stage is not running")
            stage.status = "failed"
            stage.last_error = action.reason or "unspecified failure"
            record.active_stages = [key for key in record.active_stages if key != stage.key]
            if stage.key not in record.failed_stages:
                record.failed_stages.append(stage.key)
            record.state = OrchestrationState.HUMAN_REVIEW_REQUIRED if stage.retries_used < stage.max_retries else OrchestrationState.FAILED

        elif action.command == OrchestrationCommand.RETRY_STAGE:
            stage = self._stage(record, action.stage_key)
            if stage.status != "failed" or stage.retries_used >= stage.max_retries:
                raise OrchestrationError("stage cannot be retried")
            stage.retries_used += 1
            stage.status = "ready"
            stage.last_error = None
            record.failed_stages = [key for key in record.failed_stages if key != stage.key]
            if stage.key not in record.ready_queue:
                record.ready_queue.append(stage.key)
            record.state = OrchestrationState.APPROVED

        elif action.command == OrchestrationCommand.PAUSE:
            if record.state in {OrchestrationState.COMPLETED, OrchestrationState.ARCHIVED}:
                raise OrchestrationError("terminal workflow cannot be paused")
            record.state = OrchestrationState.PAUSED

        elif action.command == OrchestrationCommand.RESUME:
            if record.state != OrchestrationState.PAUSED:
                raise OrchestrationError("workflow is not paused")
            record.state = OrchestrationState.MONITORING if record.active_stages else OrchestrationState.APPROVED

        elif action.command == OrchestrationCommand.REJECT:
            if record.state in {OrchestrationState.COMPLETED, OrchestrationState.ARCHIVED}:
                raise OrchestrationError("terminal workflow cannot be rejected")
            record.state = OrchestrationState.REJECTED
            if action.reason:
                record.decision_notes.append(action.reason)

        elif action.command == OrchestrationCommand.ARCHIVE:
            record.state = OrchestrationState.ARCHIVED

        record.updated_at = datetime.utcnow()
        self._append_audit(record, action.actor, action.command.value, before, record.state.value, {"stage_key": action.stage_key})
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def _prepare(self, record: OrchestrationRecord, payload: OrchestrationCreate, actor: str) -> None:
        before = record.state.value
        ordered = self._topological_order(payload)
        by_key = {stage.key: stage for stage in payload.stages}
        lane_end = [0] * payload.max_parallel_stages
        sequence_by_key: dict[str, int] = {}
        runtimes: list[StageRuntime] = []

        for sequence, key in enumerate(ordered, start=1):
            stage = by_key[key]
            dependency_sequence = max((sequence_by_key[dep] for dep in stage.dependencies), default=0)
            lane = min(range(len(lane_end)), key=lambda idx: lane_end[idx])
            lane_end[lane] = max(lane_end[lane], dependency_sequence) + 1
            sequence_by_key[key] = sequence
            runtimes.append(StageRuntime(
                key=stage.key,
                title=stage.title,
                module=stage.module,
                owner=stage.owner,
                sequence=sequence,
                lane=lane + 1,
                dependencies=stage.dependencies,
                timeout_seconds=stage.timeout_seconds,
                max_retries=stage.max_retries,
                requires_human_gate=stage.requires_human_gate,
                dispatch_enabled=stage.dispatch_enabled,
                rollback_action=stage.rollback_action,
                expected_output=stage.expected_output,
            ))

        record.stages = runtimes
        record.ready_queue = [stage.key for stage in runtimes if not stage.dependencies and stage.dispatch_enabled]
        for stage in record.stages:
            if stage.key in record.ready_queue:
                stage.status = "ready"

        gated = sum(1 for stage in runtimes if stage.requires_human_gate)
        disabled = sum(1 for stage in runtimes if not stage.dispatch_enabled)
        dependency_density = sum(len(stage.dependencies) for stage in runtimes) / max(1, len(runtimes))
        readiness = max(0.0, 100.0 - gated * 6 - disabled * 25 - dependency_density * 4)
        confidence = max(0.0, min(100.0, readiness - sum(stage.max_retries for stage in runtimes) / max(1, len(runtimes))))
        record.orchestration_readiness_score = round(readiness, 2)
        record.delivery_confidence_score = round(confidence, 2)
        if disabled or gated or readiness < 75 or confidence < 70:
            record.state = OrchestrationState.HUMAN_REVIEW_REQUIRED
        else:
            record.state = OrchestrationState.ORCHESTRATION_READY
        record.updated_at = datetime.utcnow()
        self._append_audit(record, actor, "prepare", before, record.state.value, {"ordered_stages": ordered})

    @staticmethod
    def _topological_order(payload: OrchestrationCreate) -> list[str]:
        indegree = {stage.key: 0 for stage in payload.stages}
        graph: dict[str, list[str]] = defaultdict(list)
        for stage in payload.stages:
            for dependency in stage.dependencies:
                graph[dependency].append(stage.key)
                indegree[stage.key] += 1
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
            raise OrchestrationError("cyclic orchestration graph detected")
        return result

    @staticmethod
    def _stage(record: OrchestrationRecord, stage_key: str | None) -> StageRuntime:
        if not stage_key:
            raise OrchestrationError("stage_key is required")
        for stage in record.stages:
            if stage.key == stage_key:
                return stage
        raise OrchestrationError("stage not found")

    @staticmethod
    def _refresh_ready_queue(record: OrchestrationRecord) -> None:
        completed = set(record.completed_stages)
        active = set(record.active_stages)
        for stage in record.stages:
            if stage.status == "pending" and stage.dispatch_enabled and set(stage.dependencies) <= completed and stage.key not in active:
                stage.status = "ready"
                if stage.key not in record.ready_queue:
                    record.ready_queue.append(stage.key)

    def _append_audit(self, record: OrchestrationRecord, actor: str, action: str, from_state: str | None, to_state: str, details: dict[str, object] | None = None) -> None:
        self._audit.append(AuditEvent(
            workspace_id=record.workspace_id,
            record_id=record.id,
            action=action,
            actor=actor,
            from_state=from_state,
            to_state=to_state,
            details=details or {},
        ))
