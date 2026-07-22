from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock

from .models import (
    AuditEvent,
    RiskDecision,
    RollbackActionRequest,
    RollbackAssessment,
    RollbackAssessmentCreate,
    RollbackRecommendation,
    RollbackState,
)


class RollbackIntelligenceError(ValueError):
    pass


class RollbackIntelligenceService:
    def __init__(self) -> None:
        self._records: dict[str, RollbackAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipts: set[str] = set()
        self._audit: list[AuditEvent] = []
        self._lock = RLock()

    def create(self, payload: RollbackAssessmentCreate, actor: str = "system") -> RollbackAssessment:
        with self._lock:
            key = (payload.workspace_id, payload.source_key)
            if key in self._source_keys:
                raise RollbackIntelligenceError("duplicate source_key in workspace")
            state = RollbackState.BLOCKED if payload.risk_decision == RiskDecision.BLOCK else RollbackState.DRAFT
            record = RollbackAssessment(**payload.model_dump(), state=state)
            self._records[record.record_id] = record
            self._source_keys.add(key)
            self._audit_event(record, "create", actor, None, state)
            return record.model_copy(deep=True)

    def get(self, workspace_id: str, record_id: str) -> RollbackAssessment:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise RollbackIntelligenceError("record not found")
        return record.model_copy(deep=True)

    def list(self, workspace_id: str) -> list[RollbackAssessment]:
        return [r.model_copy(deep=True) for r in self._records.values() if r.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [e.model_copy(deep=True) for e in self._audit if e.workspace_id == workspace_id]

    def act(self, workspace_id: str, record_id: str, request: RollbackActionRequest) -> RollbackAssessment:
        with self._lock:
            record = self._records.get(record_id)
            if not record or record.workspace_id != workspace_id:
                raise RollbackIntelligenceError("record not found")
            previous = record.state
            action = request.action

            if record.risk_decision == RiskDecision.BLOCK and action not in {"reject", "archive"}:
                raise RollbackIntelligenceError("Risk Brain hard block is authoritative")

            if action == "analyze":
                self._require(record, RollbackState.DRAFT)
                record.deterioration_score = round(
                    sum(s.normalized_deterioration() * s.weight for s in record.signals) * 100, 4
                )
                record.critical_signal_count = sum(
                    1 for s in record.signals if s.critical and s.normalized_deterioration() > 0
                )
                if record.critical_signal_count or record.deterioration_score >= 25:
                    record.recommendation = RollbackRecommendation.ROLLBACK
                elif record.deterioration_score <= 5:
                    record.recommendation = RollbackRecommendation.KEEP_CURRENT
                else:
                    record.recommendation = RollbackRecommendation.HOLD_FOR_REVIEW
                record.state = RollbackState.ANALYZED
            elif action == "request-review":
                self._require(record, RollbackState.ANALYZED)
                record.state = RollbackState.HUMAN_REVIEW_REQUIRED
            elif action == "approve":
                self._require(record, RollbackState.HUMAN_REVIEW_REQUIRED)
                self._consume_token(request.approval_token)
                record.approval_actor = request.actor
                record.state = RollbackState.APPROVED
            elif action == "queue-rollback":
                self._require(record, RollbackState.APPROVED)
                if record.recommendation != RollbackRecommendation.ROLLBACK:
                    raise RollbackIntelligenceError("assessment does not recommend rollback")
                self._consume_receipt(request.receipt_id)
                record.rollback_receipt_id = request.receipt_id
                record.state = RollbackState.ROLLBACK_QUEUED
            elif action == "execute-rollback":
                self._require(record, RollbackState.ROLLBACK_QUEUED)
                self._consume_receipt(request.receipt_id)
                record.state = RollbackState.ROLLBACK_EXECUTED
            elif action == "verify":
                self._require(record, RollbackState.ROLLBACK_EXECUTED)
                self._consume_receipt(request.receipt_id)
                if not request.verification_evidence_refs:
                    raise RollbackIntelligenceError("verification evidence is required")
                record.verification_evidence_refs = request.verification_evidence_refs
                record.state = RollbackState.VERIFIED
            elif action == "reject":
                if record.state in {RollbackState.VERIFIED, RollbackState.ARCHIVED}:
                    raise RollbackIntelligenceError("record can no longer be rejected")
                record.state = RollbackState.REJECTED
            elif action == "fail":
                if record.state == RollbackState.ARCHIVED:
                    raise RollbackIntelligenceError("archived record is immutable")
                record.state = RollbackState.FAILED
            elif action == "archive":
                if record.state not in {RollbackState.VERIFIED, RollbackState.REJECTED, RollbackState.FAILED, RollbackState.BLOCKED}:
                    raise RollbackIntelligenceError("record must be terminal before archive")
                record.state = RollbackState.ARCHIVED

            record.updated_at = datetime.now(timezone.utc)
            self._audit_event(record, action, request.actor, previous, record.state, request.note)
            return record.model_copy(deep=True)

    @staticmethod
    def _require(record: RollbackAssessment, expected: RollbackState) -> None:
        if record.state != expected:
            raise RollbackIntelligenceError(f"invalid state transition from {record.state}; expected {expected}")

    def _consume_token(self, token: str | None) -> None:
        if not token:
            raise RollbackIntelligenceError("approval_token is required")
        if token in self._approval_tokens:
            raise RollbackIntelligenceError("approval_token replay detected")
        self._approval_tokens.add(token)

    def _consume_receipt(self, receipt: str | None) -> None:
        if not receipt:
            raise RollbackIntelligenceError("receipt_id is required")
        if receipt in self._receipts:
            raise RollbackIntelligenceError("receipt replay detected")
        self._receipts.add(receipt)

    def _audit_event(self, record: RollbackAssessment, action: str, actor: str,
                     previous: RollbackState | None, target: RollbackState,
                     note: str | None = None) -> None:
        self._audit.append(AuditEvent(
            record_id=record.record_id,
            workspace_id=record.workspace_id,
            action=action,
            actor=actor,
            from_state=previous,
            to_state=target,
            details={"note": note} if note else {},
        ))
