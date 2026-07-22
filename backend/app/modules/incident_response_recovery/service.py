from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from .models import AuditEvent, IncidentAction, IncidentCreate, IncidentRecord, IncidentSeverity, IncidentState


class IncidentResponseError(ValueError):
    pass


class IncidentResponseService:
    def __init__(self) -> None:
        self._records: dict[str, IncidentRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipts: set[str] = set()
        self._audit: list[AuditEvent] = []
        self._lock = RLock()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def create(self, payload: IncidentCreate) -> IncidentRecord:
        with self._lock:
            source = (payload.workspace_id, payload.source_key)
            if source in self._source_keys:
                raise IncidentResponseError("duplicate source key")
            if payload.risk_brain_blocked:
                state = IncidentState.BLOCKED
            elif not payload.upstream_evidence_verified:
                state = IncidentState.EVIDENCE_REQUIRED
            elif payload.severity in {IncidentSeverity.CRITICAL, IncidentSeverity.EMERGENCY}:
                state = IncidentState.CONTAINMENT_REQUIRED
            else:
                state = IncidentState.OPEN
            record = IncidentRecord(**payload.model_dump(), state=state)
            self._records[record.record_id] = record
            self._source_keys.add(source)
            self._log(record, "create", "system", None)
            return record

    def list(self, workspace_id: str) -> list[IncidentRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> IncidentRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise IncidentResponseError("incident not found")
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, action: IncidentAction) -> IncidentRecord:
        with self._lock:
            record = self.get(record_id, workspace_id)
            now = datetime.now(timezone.utc)

            if action.action == "request-containment":
                self._require_state(record, IncidentState.OPEN)
                record.state = IncidentState.CONTAINMENT_REQUIRED

            elif action.action == "approve":
                self._require_state(record, IncidentState.OPEN, IncidentState.CONTAINMENT_REQUIRED, IncidentState.HUMAN_REVIEW_REQUIRED)
                if not action.approval_token:
                    raise IncidentResponseError("approval token required")
                token_hash = self._hash(action.approval_token)
                if token_hash in self._approval_tokens:
                    raise IncidentResponseError("approval token replay detected")
                self._approval_tokens.add(token_hash)
                record.approval_token_hash = token_hash
                record.state = IncidentState.APPROVED

            elif action.action == "contain":
                self._require_state(record, IncidentState.APPROVED)
                self._consume_receipt(action.receipt_id)
                self._enforce_governance(record)
                record.state = IncidentState.CONTAINED
                record.contained_at = now

            elif action.action == "start-recovery":
                self._require_state(record, IncidentState.CONTAINED)
                self._consume_receipt(action.receipt_id)
                self._enforce_governance(record)
                record.state = IncidentState.RECOVERY_IN_PROGRESS

            elif action.action == "complete-step":
                self._require_state(record, IncidentState.RECOVERY_IN_PROGRESS)
                self._consume_receipt(action.receipt_id)
                if not action.step_id:
                    raise IncidentResponseError("step id required")
                step = next((item for item in record.recovery_steps if item.step_id == action.step_id), None)
                if not step:
                    raise IncidentResponseError("recovery step not found")
                if step.completed:
                    raise IncidentResponseError("recovery step already completed")
                step.completed = True

            elif action.action == "monitor":
                self._require_state(record, IncidentState.RECOVERY_IN_PROGRESS)
                if any(not step.completed for step in record.recovery_steps):
                    raise IncidentResponseError("recovery steps incomplete")
                self._consume_receipt(action.receipt_id)
                record.state = IncidentState.MONITORING

            elif action.action == "resolve":
                self._require_state(record, IncidentState.MONITORING)
                self._consume_receipt(action.receipt_id)
                record.state = IncidentState.RESOLVED
                record.resolved_at = now

            elif action.action == "fail":
                record.state = IncidentState.FAILED

            elif action.action == "archive":
                self._require_state(record, IncidentState.RESOLVED, IncidentState.FAILED)
                record.state = IncidentState.ARCHIVED

            record.last_receipt_id = action.receipt_id or record.last_receipt_id
            record.updated_at = now
            self._log(record, action.action, action.actor_id, action.reason)
            return record

    def _enforce_governance(self, record: IncidentRecord) -> None:
        if record.risk_brain_blocked:
            raise IncidentResponseError("Risk Brain hard block")
        if not record.upstream_evidence_verified:
            raise IncidentResponseError("upstream evidence required")
        if not record.approval_token_hash:
            raise IncidentResponseError("human approval required")

    def _consume_receipt(self, receipt_id: str | None) -> None:
        if not receipt_id:
            raise IncidentResponseError("receipt id required")
        if receipt_id in self._receipts:
            raise IncidentResponseError("receipt replay detected")
        self._receipts.add(receipt_id)

    @staticmethod
    def _require_state(record: IncidentRecord, *states: IncidentState) -> None:
        if record.state not in states:
            expected = ", ".join(state.value for state in states)
            raise IncidentResponseError(f"invalid state transition from {record.state.value}; expected {expected}")

    def _log(self, record: IncidentRecord, action: str, actor_id: str, reason: str | None) -> None:
        self._audit.append(AuditEvent(event_id=str(uuid4()), record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor_id=actor_id, state=record.state, reason=reason))


service = IncidentResponseService()
