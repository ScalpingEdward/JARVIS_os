from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AuditEvent,
    LearningActionRequest,
    LearningCreate,
    LearningState,
    OperationalLearningRecord,
    OutcomeStatus,
    RiskDecision,
)


class OperationalLearningError(RuntimeError):
    pass


class OperationalLearningService:
    def __init__(self) -> None:
        self._records: dict[str, OperationalLearningRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: LearningCreate) -> OperationalLearningRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise OperationalLearningError("duplicate source key")
        record = OperationalLearningRecord(**payload.model_dump())
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> OperationalLearningRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise OperationalLearningError("operational learning record not found")
        return record

    def list(self, workspace_id: str) -> list[OperationalLearningRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: LearningActionRequest) -> OperationalLearningRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, LearningState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = LearningState.BLOCKED
            elif not record.learning_evidence_refs:
                raise OperationalLearningError("learning evidence is required")
            elif len(record.outcomes) < record.minimum_sample_size:
                raise OperationalLearningError("minimum sample size not reached")
            else:
                record.state = LearningState.EVIDENCE_READY
        elif action == "analyze":
            self._require(record, LearningState.EVIDENCE_READY)
            if not any(item.status in {OutcomeStatus.HEALTHY, OutcomeStatus.FAILED} for item in record.outcomes):
                raise OperationalLearningError("terminal recovery outcomes are required")
            record.state = LearningState.ANALYZED
        elif action == "propose":
            self._require(record, LearningState.ANALYZED)
            if not request.recommendation_ids:
                raise OperationalLearningError("recommendation_ids are required")
            known = {item.recommendation_id: item for item in record.recommendations}
            missing = set(request.recommendation_ids) - set(known)
            if missing:
                raise OperationalLearningError("unknown recommendation id")
            if any(known[item].confidence < record.minimum_confidence for item in request.recommendation_ids):
                raise OperationalLearningError("recommendation confidence below threshold")
            record.selected_recommendation_ids = list(dict.fromkeys(request.recommendation_ids))
            record.state = LearningState.RECOMMENDATIONS_PROPOSED
        elif action == "request-review":
            self._require(record, LearningState.RECOMMENDATIONS_PROPOSED)
            record.state = LearningState.HUMAN_REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, LearningState.HUMAN_REVIEW_REQUIRED)
            self._consume_token(request.approval_token)
            record.approval_actor = request.actor
            record.state = LearningState.APPROVED
        elif action == "apply":
            self._require(record, LearningState.APPROVED)
            if record.risk_decision == RiskDecision.BLOCK:
                raise OperationalLearningError("Risk Brain hard block")
            self._consume_receipt(request.receipt_id)
            record.state = LearningState.APPLIED
        elif action == "record-validation":
            if record.state not in {LearningState.APPLIED, LearningState.VALIDATING}:
                raise OperationalLearningError("record-validation requires applied or validating state")
            if request.validation_healthy is None:
                raise OperationalLearningError("validation_healthy is required")
            if not request.validation_evidence_refs:
                raise OperationalLearningError("validation evidence is required")
            self._consume_receipt(request.receipt_id)
            record.validation_cycles += 1
            record.validation_evidence_refs.extend(request.validation_evidence_refs)
            if request.validation_healthy:
                record.consecutive_healthy_cycles += 1
            else:
                record.consecutive_healthy_cycles = 0
            record.state = LearningState.VALIDATING
        elif action == "verify":
            self._require(record, LearningState.VALIDATING)
            if record.consecutive_healthy_cycles < record.validation_cycles_required:
                raise OperationalLearningError("healthy validation cycles incomplete")
            if not record.validation_evidence_refs:
                raise OperationalLearningError("validation evidence is required")
            record.state = LearningState.VERIFIED
        elif action == "reject":
            if record.state not in {
                LearningState.RECOMMENDATIONS_PROPOSED,
                LearningState.HUMAN_REVIEW_REQUIRED,
                LearningState.APPROVED,
            }:
                raise OperationalLearningError("record cannot be rejected in current state")
            record.state = LearningState.REJECTED
        elif action == "fail":
            if record.state not in {LearningState.APPLIED, LearningState.VALIDATING}:
                raise OperationalLearningError("record cannot fail in current state")
            record.state = LearningState.FAILED
        elif action == "archive":
            if record.state not in {
                LearningState.BLOCKED,
                LearningState.VERIFIED,
                LearningState.REJECTED,
                LearningState.FAILED,
            }:
                raise OperationalLearningError("only terminal records can be archived")
            record.state = LearningState.ARCHIVED
        else:
            raise OperationalLearningError("unsupported action")

        self._touch(record)
        self._emit(
            record,
            action,
            request.actor,
            before,
            record.state,
            {
                "recommendation_ids": request.recommendation_ids,
                "validation_healthy": request.validation_healthy,
                "note": request.note,
            },
        )
        return record

    def _require(self, record: OperationalLearningRecord, expected: LearningState) -> None:
        if record.state != expected:
            raise OperationalLearningError(f"action requires {expected.value} state")

    def _consume_token(self, token: str | None) -> None:
        if not token:
            raise OperationalLearningError("approval token is required")
        if token in self._approval_tokens:
            raise OperationalLearningError("approval token replay detected")
        self._approval_tokens.add(token)

    def _consume_receipt(self, receipt_id: str | None) -> None:
        if not receipt_id:
            raise OperationalLearningError("receipt_id is required")
        if receipt_id in self._receipt_ids:
            raise OperationalLearningError("receipt replay detected")
        self._receipt_ids.add(receipt_id)

    def _touch(self, record: OperationalLearningRecord) -> None:
        record.updated_at = datetime.now(timezone.utc)

    def _emit(
        self,
        record: OperationalLearningRecord,
        action: str,
        actor: str,
        from_state: LearningState | None,
        to_state: LearningState,
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


service = OperationalLearningService()
