from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from .models import (
    AuditEvent,
    FindingSeverity,
    ResilienceReviewAction,
    ResilienceReviewCreate,
    ResilienceReviewRecord,
    ReviewState,
)


class PostIncidentResilienceError(ValueError):
    pass


class PostIncidentResilienceService:
    def __init__(self) -> None:
        self._records: dict[str, ResilienceReviewRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipts: set[str] = set()
        self._audit: list[AuditEvent] = []
        self._lock = RLock()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def create(self, payload: ResilienceReviewCreate) -> ResilienceReviewRecord:
        with self._lock:
            source = (payload.workspace_id, payload.source_key)
            if source in self._source_keys:
                raise PostIncidentResilienceError("duplicate source key")
            if payload.risk_brain_blocked:
                state = ReviewState.BLOCKED
            elif not payload.upstream_evidence_verified:
                state = ReviewState.EVIDENCE_REQUIRED
            else:
                state = ReviewState.DRAFT
            record = ResilienceReviewRecord(
                record_id=str(uuid4()),
                workspace_id=payload.workspace_id,
                source_key=payload.source_key,
                incident_record_id=payload.incident_record_id,
                reconciliation_record_id=payload.reconciliation_record_id,
                runtime_record_id=payload.runtime_record_id,
                root_cause=payload.root_cause,
                impact_summary=payload.impact_summary,
                findings=payload.findings,
                metrics=payload.metrics,
                state=state,
                risk_brain_blocked=payload.risk_brain_blocked,
                upstream_evidence_verified=payload.upstream_evidence_verified,
            )
            self._records[record.record_id] = record
            self._source_keys.add(source)
            self._log(record, "create", "system", None)
            return record

    def list(self, workspace_id: str) -> list[ResilienceReviewRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> ResilienceReviewRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise PostIncidentResilienceError("review not found")
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, action: ResilienceReviewAction) -> ResilienceReviewRecord:
        with self._lock:
            record = self.get(record_id, workspace_id)
            now = datetime.now(timezone.utc)

            if action.action == "analyze":
                self._require_state(record, ReviewState.DRAFT)
                self._enforce_governance(record)
                record.critical_findings = sum(1 for item in record.findings if item.severity == FindingSeverity.CRITICAL)
                total = len(record.findings) or 1
                weighted = sum(
                    1 if item.severity == FindingSeverity.INFO else 2 if item.severity == FindingSeverity.WARNING else 4
                    for item in record.findings
                )
                record.resilience_score = max(0.0, round(100.0 - (weighted / total) * 15.0, 2))
                record.state = ReviewState.HUMAN_REVIEW_REQUIRED

            elif action.action == "approve":
                self._require_state(record, ReviewState.HUMAN_REVIEW_REQUIRED)
                if not action.approval_token:
                    raise PostIncidentResilienceError("approval token required")
                token_hash = self._hash(action.approval_token)
                if token_hash in self._approval_tokens:
                    raise PostIncidentResilienceError("approval token replay detected")
                self._approval_tokens.add(token_hash)
                record.approval_token_hash = token_hash
                record.state = ReviewState.APPROVED

            elif action.action == "queue-improvement":
                self._require_state(record, ReviewState.APPROVED)
                self._consume_receipt(action.receipt_id)
                self._enforce_governance(record)
                record.state = ReviewState.IMPROVEMENT_QUEUED

            elif action.action == "verify":
                self._require_state(record, ReviewState.IMPROVEMENT_QUEUED)
                self._consume_receipt(action.receipt_id)
                expected = {item.finding_id for item in record.findings}
                completed = set(action.completed_finding_ids)
                if not expected.issubset(completed):
                    raise PostIncidentResilienceError("all resilience findings must be completed")
                record.completed_finding_ids = sorted(completed)
                record.state = ReviewState.VERIFIED

            elif action.action == "reject":
                self._require_state(record, ReviewState.HUMAN_REVIEW_REQUIRED, ReviewState.APPROVED)
                record.state = ReviewState.REJECTED

            elif action.action == "archive":
                self._require_state(record, ReviewState.VERIFIED, ReviewState.REJECTED)
                record.state = ReviewState.ARCHIVED

            record.last_receipt_id = action.receipt_id or record.last_receipt_id
            record.updated_at = now
            self._log(record, action.action, action.actor_id, action.reason)
            return record

    def _enforce_governance(self, record: ResilienceReviewRecord) -> None:
        if record.risk_brain_blocked:
            raise PostIncidentResilienceError("Risk Brain hard block")
        if not record.upstream_evidence_verified:
            raise PostIncidentResilienceError("upstream evidence required")

    def _consume_receipt(self, receipt_id: str | None) -> None:
        if not receipt_id:
            raise PostIncidentResilienceError("receipt id required")
        if receipt_id in self._receipts:
            raise PostIncidentResilienceError("receipt replay detected")
        self._receipts.add(receipt_id)

    @staticmethod
    def _require_state(record: ResilienceReviewRecord, *states: ReviewState) -> None:
        if record.state not in states:
            expected = ", ".join(state.value for state in states)
            raise PostIncidentResilienceError(
                f"invalid state transition from {record.state.value}; expected {expected}"
            )

    def _log(self, record: ResilienceReviewRecord, action: str, actor_id: str, reason: str | None) -> None:
        self._audit.append(
            AuditEvent(
                event_id=str(uuid4()),
                record_id=record.record_id,
                workspace_id=record.workspace_id,
                action=action,
                actor_id=actor_id,
                state=record.state,
                reason=reason,
            )
        )


service = PostIncidentResilienceService()
