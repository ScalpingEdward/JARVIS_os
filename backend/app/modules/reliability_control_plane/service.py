from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from .models import AuditEvent, ReliabilityAction, ReliabilityBand, ReliabilityCreate, ReliabilityRecord, ReliabilityState


class ReliabilityControlPlaneError(ValueError):
    pass


class ReliabilityControlPlaneService:
    def __init__(self) -> None:
        self._records: dict[str, ReliabilityRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipts: set[str] = set()
        self._audit: list[AuditEvent] = []
        self._lock = RLock()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def create(self, payload: ReliabilityCreate) -> ReliabilityRecord:
        with self._lock:
            source = (payload.workspace_id, payload.source_key)
            if source in self._source_keys:
                raise ReliabilityControlPlaneError("duplicate source key")
            if payload.risk_brain_blocked:
                state = ReliabilityState.BLOCKED
            elif not payload.upstream_evidence_verified:
                state = ReliabilityState.EVIDENCE_REQUIRED
            else:
                state = ReliabilityState.DRAFT
            record = ReliabilityRecord(record_id=str(uuid4()), state=state, **payload.model_dump())
            self._records[record.record_id] = record
            self._source_keys.add(source)
            self._log(record, "create", "system", None)
            return record

    def list(self, workspace_id: str) -> list[ReliabilityRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> ReliabilityRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise ReliabilityControlPlaneError("reliability assessment not found")
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, action: ReliabilityAction) -> ReliabilityRecord:
        with self._lock:
            record = self.get(record_id, workspace_id)
            if action.action == "score":
                self._require_state(record, ReliabilityState.DRAFT)
                self._enforce_governance(record)
                record.score = self._score(record)
                record.band = self._band(record.score)
                record.state = ReliabilityState.SCORED
            elif action.action == "request-review":
                self._require_state(record, ReliabilityState.SCORED)
                record.state = ReliabilityState.HUMAN_REVIEW_REQUIRED
            elif action.action == "approve":
                self._require_state(record, ReliabilityState.HUMAN_REVIEW_REQUIRED)
                if not action.approval_token:
                    raise ReliabilityControlPlaneError("approval token required")
                token_hash = self._hash(action.approval_token)
                if token_hash in self._approval_tokens:
                    raise ReliabilityControlPlaneError("approval token replay detected")
                self._approval_tokens.add(token_hash)
                record.approval_token_hash = token_hash
                record.state = ReliabilityState.APPROVED
            elif action.action == "queue-optimization":
                self._require_state(record, ReliabilityState.APPROVED)
                self._consume_receipt(action.receipt_id)
                if not record.proposals:
                    raise ReliabilityControlPlaneError("optimization proposals required")
                record.state = ReliabilityState.OPTIMIZATION_QUEUED
            elif action.action == "apply":
                self._require_state(record, ReliabilityState.OPTIMIZATION_QUEUED)
                self._consume_receipt(action.receipt_id)
                known = {item.proposal_id for item in record.proposals}
                selected = set(action.applied_proposal_ids)
                if not selected or not selected.issubset(known):
                    raise ReliabilityControlPlaneError("unknown or empty optimization proposal selection")
                record.applied_proposal_ids = sorted(selected)
                record.state = ReliabilityState.APPLIED
            elif action.action == "verify":
                self._require_state(record, ReliabilityState.APPLIED)
                self._consume_receipt(action.receipt_id)
                if action.verification_passed is not True:
                    raise ReliabilityControlPlaneError("optimization verification failed")
                record.state = ReliabilityState.VERIFIED
            elif action.action == "reject":
                self._require_state(record, ReliabilityState.SCORED, ReliabilityState.HUMAN_REVIEW_REQUIRED)
                record.state = ReliabilityState.REJECTED
            elif action.action == "archive":
                self._require_state(record, ReliabilityState.VERIFIED, ReliabilityState.REJECTED)
                record.state = ReliabilityState.ARCHIVED
            record.last_receipt_id = action.receipt_id or record.last_receipt_id
            record.updated_at = datetime.now(timezone.utc)
            self._log(record, action.action, action.actor_id, action.reason)
            return record

    def _score(self, record: ReliabilityRecord) -> float:
        total = 0.0
        for metric in record.metrics:
            if metric.target_value == 0:
                normalized = 1.0 if metric.observed_value == 0 else 0.0
            elif metric.higher_is_better:
                normalized = min(max(metric.observed_value / metric.target_value, 0.0), 1.0)
            else:
                normalized = min(max(metric.target_value / metric.observed_value, 0.0), 1.0) if metric.observed_value else 1.0
            total += normalized * metric.weight
        return round(total * 100, 2)

    @staticmethod
    def _band(score: float) -> ReliabilityBand:
        if score < 40:
            return ReliabilityBand.CRITICAL
        if score < 60:
            return ReliabilityBand.WEAK
        if score < 75:
            return ReliabilityBand.STABLE
        if score < 90:
            return ReliabilityBand.STRONG
        return ReliabilityBand.EXCELLENT

    def _enforce_governance(self, record: ReliabilityRecord) -> None:
        if record.risk_brain_blocked:
            raise ReliabilityControlPlaneError("Risk Brain hard block")
        if not record.upstream_evidence_verified:
            raise ReliabilityControlPlaneError("upstream evidence required")

    def _consume_receipt(self, receipt_id: str | None) -> None:
        if not receipt_id:
            raise ReliabilityControlPlaneError("receipt id required")
        if receipt_id in self._receipts:
            raise ReliabilityControlPlaneError("receipt replay detected")
        self._receipts.add(receipt_id)

    @staticmethod
    def _require_state(record: ReliabilityRecord, *states: ReliabilityState) -> None:
        if record.state not in states:
            expected = ", ".join(item.value for item in states)
            raise ReliabilityControlPlaneError(f"invalid state transition from {record.state.value}; expected {expected}")

    def _log(self, record: ReliabilityRecord, action: str, actor_id: str, reason: str | None) -> None:
        self._audit.append(AuditEvent(event_id=str(uuid4()), record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor_id=actor_id, state=record.state, reason=reason))


service = ReliabilityControlPlaneService()
