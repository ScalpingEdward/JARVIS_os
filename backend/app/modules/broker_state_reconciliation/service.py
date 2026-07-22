from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from .models import (
    AuditEvent,
    DriftItem,
    DriftSeverity,
    ReconciliationAction,
    ReconciliationCreate,
    ReconciliationRecord,
    ReconciliationState,
)


class BrokerStateReconciliationError(ValueError):
    pass


class BrokerStateReconciliationService:
    def __init__(self) -> None:
        self._records: dict[str, ReconciliationRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipts: set[str] = set()
        self._audit: list[AuditEvent] = []
        self._lock = RLock()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def create(self, payload: ReconciliationCreate) -> ReconciliationRecord:
        with self._lock:
            source = (payload.workspace_id, payload.source_key)
            if source in self._source_keys:
                raise BrokerStateReconciliationError("duplicate source key")
            if payload.expected_snapshot.account_ref != payload.broker_snapshot.account_ref:
                raise BrokerStateReconciliationError("account reference mismatch")

            drifts = self._compare(payload)
            if payload.risk_brain_blocked:
                state = ReconciliationState.BLOCKED
            elif not payload.upstream_evidence_verified:
                state = ReconciliationState.EVIDENCE_REQUIRED
            elif drifts:
                state = ReconciliationState.HUMAN_REVIEW_REQUIRED
            else:
                state = ReconciliationState.MATCHED

            record = ReconciliationRecord(
                record_id=str(uuid4()),
                workspace_id=payload.workspace_id,
                source_key=payload.source_key,
                runtime_record_id=payload.runtime_record_id,
                command_record_ids=payload.command_record_ids,
                expected_snapshot=payload.expected_snapshot,
                broker_snapshot=payload.broker_snapshot,
                drifts=drifts,
                state=state,
                risk_brain_blocked=payload.risk_brain_blocked,
                upstream_evidence_verified=payload.upstream_evidence_verified,
            )
            self._records[record.record_id] = record
            self._source_keys.add(source)
            self._log(record, "create", "system", None)
            return record

    def list(self, workspace_id: str) -> list[ReconciliationRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> ReconciliationRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise BrokerStateReconciliationError("reconciliation not found")
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, action: ReconciliationAction) -> ReconciliationRecord:
        with self._lock:
            record = self.get(record_id, workspace_id)
            if action.action == "approve":
                self._require_state(record, ReconciliationState.HUMAN_REVIEW_REQUIRED)
                if not action.approval_token:
                    raise BrokerStateReconciliationError("approval token required")
                token_hash = self._hash(action.approval_token)
                if token_hash in self._approval_tokens:
                    raise BrokerStateReconciliationError("approval token replay detected")
                self._approval_tokens.add(token_hash)
                record.approval_token_hash = token_hash
                record.state = ReconciliationState.APPROVED

            elif action.action == "queue-correction":
                self._require_state(record, ReconciliationState.APPROVED)
                self._consume_receipt(action.receipt_id)
                self._enforce_governance(record)
                record.state = ReconciliationState.CORRECTION_QUEUED

            elif action.action == "resolve":
                self._require_state(record, ReconciliationState.CORRECTION_QUEUED, ReconciliationState.MATCHED)
                self._consume_receipt(action.receipt_id)
                record.state = ReconciliationState.RESOLVED

            elif action.action == "fail":
                record.state = ReconciliationState.FAILED

            elif action.action == "archive":
                self._require_state(record, ReconciliationState.RESOLVED, ReconciliationState.FAILED, ReconciliationState.MATCHED)
                record.state = ReconciliationState.ARCHIVED

            record.last_receipt_id = action.receipt_id or record.last_receipt_id
            record.updated_at = datetime.now(timezone.utc)
            self._log(record, action.action, action.actor_id, action.reason)
            return record

    def _compare(self, payload: ReconciliationCreate) -> list[DriftItem]:
        expected = payload.expected_snapshot
        actual = payload.broker_snapshot
        drifts: list[DriftItem] = []

        self._numeric_drift(drifts, "balance", expected.balance, actual.balance, payload.balance_tolerance)
        self._numeric_drift(drifts, "equity", expected.equity, actual.equity, payload.equity_tolerance)
        self._numeric_drift(drifts, "margin_used", expected.margin_used, actual.margin_used, payload.equity_tolerance)

        expected_positions = {item.position_id: item for item in expected.positions}
        actual_positions = {item.position_id: item for item in actual.positions}
        for position_id in sorted(expected_positions.keys() - actual_positions.keys()):
            drifts.append(DriftItem(field=f"position:{position_id}", expected="present", actual="missing", severity=DriftSeverity.CRITICAL))
        for position_id in sorted(actual_positions.keys() - expected_positions.keys()):
            drifts.append(DriftItem(field=f"position:{position_id}", expected="absent", actual="unexpected", severity=DriftSeverity.CRITICAL))
        for position_id in sorted(expected_positions.keys() & actual_positions.keys()):
            left, right = expected_positions[position_id], actual_positions[position_id]
            if left.symbol != right.symbol or left.side != right.side:
                drifts.append(DriftItem(field=f"position:{position_id}:identity", expected=f"{left.symbol}:{left.side}", actual=f"{right.symbol}:{right.side}", severity=DriftSeverity.CRITICAL))
            self._numeric_drift(drifts, f"position:{position_id}:volume", left.volume, right.volume, payload.volume_tolerance)
            self._numeric_drift(drifts, f"position:{position_id}:entry_price", left.entry_price, right.entry_price, payload.equity_tolerance)
        return drifts

    @staticmethod
    def _numeric_drift(drifts: list[DriftItem], field: str, expected: float, actual: float, tolerance: float) -> None:
        delta = abs(expected - actual)
        if delta <= tolerance:
            return
        severity = DriftSeverity.CRITICAL if tolerance == 0 or delta > max(tolerance * 10, 1.0) else DriftSeverity.WARNING
        drifts.append(DriftItem(field=field, expected=str(expected), actual=str(actual), severity=severity))

    def _enforce_governance(self, record: ReconciliationRecord) -> None:
        if record.risk_brain_blocked:
            raise BrokerStateReconciliationError("Risk Brain hard block")
        if not record.upstream_evidence_verified:
            raise BrokerStateReconciliationError("upstream evidence required")
        if not record.approval_token_hash:
            raise BrokerStateReconciliationError("human approval required")

    def _consume_receipt(self, receipt_id: str | None) -> None:
        if not receipt_id:
            raise BrokerStateReconciliationError("receipt id required")
        if receipt_id in self._receipts:
            raise BrokerStateReconciliationError("receipt replay detected")
        self._receipts.add(receipt_id)

    @staticmethod
    def _require_state(record: ReconciliationRecord, *states: ReconciliationState) -> None:
        if record.state not in states:
            expected = ", ".join(state.value for state in states)
            raise BrokerStateReconciliationError(f"invalid state transition from {record.state.value}; expected {expected}")

    def _log(self, record: ReconciliationRecord, action: str, actor_id: str, reason: str | None) -> None:
        self._audit.append(AuditEvent(event_id=str(uuid4()), record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor_id=actor_id, state=record.state, reason=reason))


service = BrokerStateReconciliationService()
