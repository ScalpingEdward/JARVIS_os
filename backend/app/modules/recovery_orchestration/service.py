from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AuditEvent,
    OrchestrationActionRequest,
    OrchestrationCreate,
    OrchestrationState,
    RecoveryOrchestration,
    RiskDecision,
    TaskExecution,
)


class RecoveryOrchestrationError(RuntimeError):
    pass


class RecoveryOrchestrationService:
    def __init__(self) -> None:
        self._records: dict[str, RecoveryOrchestration] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: OrchestrationCreate) -> RecoveryOrchestration:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise RecoveryOrchestrationError("duplicate source key")
        record = RecoveryOrchestration(
            **payload.model_dump(),
            execution={task.task_id: TaskExecution(task_id=task.task_id) for task in payload.tasks},
        )
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> RecoveryOrchestration:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise RecoveryOrchestrationError("orchestration not found")
        return record

    def list(self, workspace_id: str) -> list[RecoveryOrchestration]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: OrchestrationActionRequest) -> RecoveryOrchestration:
        record = self.get(record_id, workspace_id)
        before = record.state

        if request.action == "validate":
            self._require(record, OrchestrationState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = OrchestrationState.BLOCKED
            elif not record.planning_evidence_refs or not record.runtime_evidence_refs:
                raise RecoveryOrchestrationError("planning and runtime evidence are required")
            else:
                record.state = OrchestrationState.VALIDATED
        elif request.action == "request-review":
            self._require(record, OrchestrationState.VALIDATED)
            record.state = OrchestrationState.HUMAN_REVIEW_REQUIRED
        elif request.action == "approve":
            self._require(record, OrchestrationState.HUMAN_REVIEW_REQUIRED)
            self._consume_token(request.approval_token)
            record.approval_actor = request.actor
            record.state = OrchestrationState.APPROVED
        elif request.action == "schedule":
            self._require(record, OrchestrationState.APPROVED)
            self._consume_receipt(request.receipt_id)
            record.state = OrchestrationState.SCHEDULED
        elif request.action == "start":
            self._require(record, OrchestrationState.SCHEDULED)
            self._consume_receipt(request.receipt_id)
            record.state = OrchestrationState.RUNNING
        elif request.action in {"complete-task", "fail-task"}:
            self._require(record, OrchestrationState.RUNNING)
            task = self._task(record, request.task_id)
            execution = record.execution[task.task_id]
            if execution.completed or execution.failed:
                raise RecoveryOrchestrationError("task already terminal")
            if any(not record.execution[item].completed for item in task.depends_on):
                raise RecoveryOrchestrationError("task dependencies are incomplete")
            if request.attempt != execution.attempts + 1:
                raise RecoveryOrchestrationError("attempt sequence mismatch")
            if request.attempt > task.max_attempts:
                raise RecoveryOrchestrationError("maximum task attempts exceeded")
            receipt = self._consume_receipt(request.receipt_id)
            execution.attempts = request.attempt
            execution.receipt_ids.append(receipt)
            execution.evidence_refs.extend(request.evidence_refs)
            execution.running = False
            if request.action == "complete-task":
                if not request.evidence_refs:
                    raise RecoveryOrchestrationError("task completion evidence is required")
                execution.completed = True
                if all(item.completed for item in record.execution.values()):
                    record.state = OrchestrationState.COMPLETED
            else:
                execution.failed = True
                record.state = OrchestrationState.FAILED
        elif request.action == "pause":
            self._require(record, OrchestrationState.RUNNING)
            record.state = OrchestrationState.PAUSED
        elif request.action == "resume":
            self._require(record, OrchestrationState.PAUSED)
            self._consume_receipt(request.receipt_id)
            record.state = OrchestrationState.RUNNING
        elif request.action == "verify":
            self._require(record, OrchestrationState.COMPLETED)
            if not request.evidence_refs:
                raise RecoveryOrchestrationError("verification evidence is required")
            self._consume_receipt(request.receipt_id)
            record.verification_evidence_refs.extend(request.evidence_refs)
            record.state = OrchestrationState.VERIFIED
        elif request.action == "cancel":
            if record.state in {OrchestrationState.VERIFIED, OrchestrationState.ARCHIVED}:
                raise RecoveryOrchestrationError("terminal orchestration cannot be cancelled")
            self._consume_receipt(request.receipt_id)
            record.state = OrchestrationState.CANCELLED
        elif request.action == "archive":
            if record.state not in {OrchestrationState.VERIFIED, OrchestrationState.FAILED, OrchestrationState.CANCELLED, OrchestrationState.BLOCKED}:
                raise RecoveryOrchestrationError("only terminal orchestration can be archived")
            record.state = OrchestrationState.ARCHIVED

        self._touch(record)
        self._emit(record, request.action, request.actor, before, record.state, {"task_id": request.task_id})
        return record

    @staticmethod
    def _task(record: RecoveryOrchestration, task_id: str | None):
        if not task_id:
            raise RecoveryOrchestrationError("task_id is required")
        for task in record.tasks:
            if task.task_id == task_id:
                return task
        raise RecoveryOrchestrationError("known task_id is required")

    @staticmethod
    def _require(record: RecoveryOrchestration, state: OrchestrationState) -> None:
        if record.state != state:
            raise RecoveryOrchestrationError(f"action requires state {state.value}")

    def _consume_token(self, token: str | None) -> str:
        if not token:
            raise RecoveryOrchestrationError("approval token is required")
        if token in self._approval_tokens:
            raise RecoveryOrchestrationError("approval token replay")
        self._approval_tokens.add(token)
        return token

    def _consume_receipt(self, receipt: str | None) -> str:
        if not receipt:
            raise RecoveryOrchestrationError("receipt_id is required")
        if receipt in self._receipt_ids:
            raise RecoveryOrchestrationError("receipt replay")
        self._receipt_ids.add(receipt)
        return receipt

    @staticmethod
    def _touch(record: RecoveryOrchestration) -> None:
        record.updated_at = datetime.now(timezone.utc)

    def _emit(self, record, action, actor, before, after, details=None) -> None:
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, details=details or {}))


service = RecoveryOrchestrationService()
