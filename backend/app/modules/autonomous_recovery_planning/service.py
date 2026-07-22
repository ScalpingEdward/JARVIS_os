from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AuditEvent,
    RecoveryActionRequest,
    RecoveryPlan,
    RecoveryPlanCreate,
    RecoveryState,
    RiskDecision,
    StepExecution,
)


class AutonomousRecoveryPlanningError(RuntimeError):
    pass


class AutonomousRecoveryPlanningService:
    def __init__(self) -> None:
        self._records: dict[str, RecoveryPlan] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: RecoveryPlanCreate) -> RecoveryPlan:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise AutonomousRecoveryPlanningError("duplicate source key")
        record = RecoveryPlan(
            **payload.model_dump(),
            execution={step.step_id: StepExecution(step_id=step.step_id) for step in payload.steps},
        )
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> RecoveryPlan:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise AutonomousRecoveryPlanningError("recovery plan not found")
        return record

    def list(self, workspace_id: str) -> list[RecoveryPlan]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: RecoveryActionRequest) -> RecoveryPlan:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "plan":
            self._require(record, RecoveryState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                raise AutonomousRecoveryPlanningError("Risk Brain hard block")
            if not record.assurance_evidence_refs or not record.runtime_evidence_refs:
                record.state = RecoveryState.EVIDENCE_REQUIRED
                self._touch(record)
                self._emit(record, action, request.actor, before, record.state)
                return record
            record.state = RecoveryState.PLANNED
        elif action == "request-review":
            self._require(record, RecoveryState.PLANNED)
            record.state = RecoveryState.HUMAN_REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, RecoveryState.HUMAN_REVIEW_REQUIRED)
            token = self._consume_token(request.approval_token)
            record.approval_actor = request.actor
            record.state = RecoveryState.APPROVED
            request.approval_token = token
        elif action == "queue":
            self._require(record, RecoveryState.APPROVED)
            self._consume_receipt(request.receipt_id)
            record.state = RecoveryState.QUEUED
        elif action == "start":
            self._require(record, RecoveryState.QUEUED)
            self._consume_receipt(request.receipt_id)
            record.state = RecoveryState.EXECUTING
        elif action == "complete-step":
            self._require(record, RecoveryState.EXECUTING)
            if not request.step_id or request.step_id not in record.execution:
                raise AutonomousRecoveryPlanningError("known step_id is required")
            execution = record.execution[request.step_id]
            step = next(item for item in record.steps if item.step_id == request.step_id)
            unfinished_dependencies = [dependency for dependency in step.depends_on if not record.execution[dependency].completed]
            if unfinished_dependencies:
                raise AutonomousRecoveryPlanningError("step dependencies are not completed")
            expected_attempt = execution.attempts + 1
            if request.attempt != expected_attempt:
                raise AutonomousRecoveryPlanningError("attempt sequence mismatch")
            if expected_attempt > step.max_attempts:
                raise AutonomousRecoveryPlanningError("maximum recovery attempts exceeded")
            receipt = self._consume_receipt(request.receipt_id)
            if not request.execution_evidence_refs:
                raise AutonomousRecoveryPlanningError("execution evidence is required")
            execution.attempts = expected_attempt
            execution.completed = True
            execution.receipt_ids.append(receipt)
            execution.execution_evidence_refs.extend(request.execution_evidence_refs)
            record.execution[request.step_id] = execution
        elif action == "verify":
            self._require(record, RecoveryState.EXECUTING)
            if not all(execution.completed for execution in record.execution.values()):
                raise AutonomousRecoveryPlanningError("all recovery steps must be completed")
            self._consume_receipt(request.receipt_id)
            if not request.verification_evidence_refs:
                raise AutonomousRecoveryPlanningError("verification evidence is required")
            record.verification_evidence_refs = request.verification_evidence_refs
            record.state = RecoveryState.VERIFIED
        elif action == "reject":
            if record.state not in {RecoveryState.HUMAN_REVIEW_REQUIRED, RecoveryState.APPROVED}:
                raise AutonomousRecoveryPlanningError("invalid state transition")
            record.state = RecoveryState.REJECTED
        elif action == "fail":
            if record.state not in {RecoveryState.QUEUED, RecoveryState.EXECUTING}:
                raise AutonomousRecoveryPlanningError("invalid state transition")
            record.state = RecoveryState.FAILED
        elif action == "archive":
            if record.state not in {RecoveryState.VERIFIED, RecoveryState.REJECTED, RecoveryState.FAILED}:
                raise AutonomousRecoveryPlanningError("invalid state transition")
            record.state = RecoveryState.ARCHIVED
        else:
            raise AutonomousRecoveryPlanningError("unsupported action")

        self._touch(record)
        self._emit(record, action, request.actor, before, record.state, request.model_dump(exclude_none=True))
        return record

    @staticmethod
    def _require(record: RecoveryPlan, expected: RecoveryState) -> None:
        if record.state != expected:
            raise AutonomousRecoveryPlanningError(
                f"invalid state transition from {record.state.value}; expected {expected.value}"
            )

    def _consume_token(self, token: str | None) -> str:
        if not token:
            raise AutonomousRecoveryPlanningError("approval token is required")
        if token in self._approval_tokens:
            raise AutonomousRecoveryPlanningError("approval token replay detected")
        self._approval_tokens.add(token)
        return token

    def _consume_receipt(self, receipt: str | None) -> str:
        if not receipt:
            raise AutonomousRecoveryPlanningError("receipt_id is required")
        if receipt in self._receipt_ids:
            raise AutonomousRecoveryPlanningError("receipt replay detected")
        self._receipt_ids.add(receipt)
        return receipt

    @staticmethod
    def _touch(record: RecoveryPlan) -> None:
        record.updated_at = datetime.now(timezone.utc)

    def _emit(
        self,
        record: RecoveryPlan,
        action: str,
        actor: str,
        from_state: RecoveryState | None,
        to_state: RecoveryState,
        details: dict | None = None,
    ) -> None:
        self._audit.append(
            AuditEvent(
                record_id=record.record_id,
                workspace_id=record.workspace_id,
                action=action,
                actor=actor,
                from_state=from_state,
                to_state=to_state,
                details=details or {},
            )
        )


service = AutonomousRecoveryPlanningService()
