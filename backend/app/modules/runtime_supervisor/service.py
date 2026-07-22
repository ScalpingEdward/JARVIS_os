from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from .models import AuditEvent, HealthState, RuntimeAction, RuntimeCreate, RuntimeRecord, RuntimeState


class RuntimeSupervisorError(ValueError):
    pass


class RuntimeSupervisorService:
    def __init__(self) -> None:
        self._records: dict[str, RuntimeRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipts: set[str] = set()
        self._audit: list[AuditEvent] = []
        self._lock = RLock()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def create(self, payload: RuntimeCreate) -> RuntimeRecord:
        with self._lock:
            source = (payload.workspace_id, payload.source_key)
            if source in self._source_keys:
                raise RuntimeSupervisorError("duplicate source key")

            if payload.risk_brain_blocked:
                state = RuntimeState.BLOCKED
            elif not payload.upstream_evidence_verified:
                state = RuntimeState.EVIDENCE_REQUIRED
            else:
                state = RuntimeState.HUMAN_REVIEW_REQUIRED

            record = RuntimeRecord(
                record_id=str(uuid4()),
                workspace_id=payload.workspace_id,
                source_key=payload.source_key,
                runtime_name=payload.runtime_name,
                broker_adapter=payload.broker_adapter,
                account_ref=payload.account_ref,
                active_policy_record_id=payload.active_policy_record_id,
                workflow_record_id=payload.workflow_record_id,
                command_record_ids=payload.command_record_ids,
                heartbeat_timeout_seconds=payload.heartbeat_timeout_seconds,
                max_consecutive_failures=payload.max_consecutive_failures,
                restart_limit=payload.restart_limit,
                dependencies=payload.dependencies,
                state=state,
                risk_brain_blocked=payload.risk_brain_blocked,
                upstream_evidence_verified=payload.upstream_evidence_verified,
            )
            self._records[record.record_id] = record
            self._source_keys.add(source)
            self._log(record, "create", "system", None)
            return record

    def list(self, workspace_id: str) -> list[RuntimeRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> RuntimeRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise RuntimeSupervisorError("runtime not found")
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, action: RuntimeAction) -> RuntimeRecord:
        with self._lock:
            record = self.get(record_id, workspace_id)
            now = datetime.now(timezone.utc)

            if action.action == "approve":
                self._require_state(record, RuntimeState.HUMAN_REVIEW_REQUIRED)
                if not action.approval_token:
                    raise RuntimeSupervisorError("approval token required")
                token_hash = self._hash(action.approval_token)
                if token_hash in self._approval_tokens:
                    raise RuntimeSupervisorError("approval token replay detected")
                self._approval_tokens.add(token_hash)
                record.approval_token_hash = token_hash
                record.state = RuntimeState.APPROVED

            elif action.action == "start":
                self._require_state(record, RuntimeState.APPROVED, RuntimeState.STOPPED)
                self._consume_receipt(action.receipt_id)
                self._enforce_governance(record)
                record.state = RuntimeState.STARTING
                record.state = self._health_state(record)
                record.last_heartbeat_at = now

            elif action.action == "heartbeat":
                self._require_state(record, RuntimeState.HEALTHY, RuntimeState.DEGRADED, RuntimeState.STARTING)
                self._consume_receipt(action.receipt_id)
                if action.dependency_updates:
                    record.dependencies = action.dependency_updates
                record.last_heartbeat_at = now
                record.consecutive_failures = 0
                record.state = self._health_state(record)

            elif action.action == "degrade":
                self._require_state(record, RuntimeState.HEALTHY, RuntimeState.STARTING)
                record.consecutive_failures += 1
                record.state = RuntimeState.DEGRADED
                if record.consecutive_failures >= record.max_consecutive_failures:
                    record.state = RuntimeState.CIRCUIT_OPEN

            elif action.action == "open-circuit":
                self._require_state(record, RuntimeState.HEALTHY, RuntimeState.DEGRADED, RuntimeState.STARTING)
                record.state = RuntimeState.CIRCUIT_OPEN

            elif action.action == "restart":
                self._require_state(record, RuntimeState.CIRCUIT_OPEN, RuntimeState.FAILED)
                self._consume_receipt(action.receipt_id)
                if record.restart_count >= record.restart_limit:
                    raise RuntimeSupervisorError("restart limit exhausted")
                self._enforce_governance(record)
                record.restart_count += 1
                record.consecutive_failures = 0
                record.state = RuntimeState.STARTING

            elif action.action == "stop":
                self._require_state(record, RuntimeState.HEALTHY, RuntimeState.DEGRADED, RuntimeState.CIRCUIT_OPEN, RuntimeState.STARTING)
                self._consume_receipt(action.receipt_id)
                record.state = RuntimeState.STOPPING
                record.state = RuntimeState.STOPPED

            elif action.action == "fail":
                record.consecutive_failures += 1
                record.state = RuntimeState.FAILED

            elif action.action == "archive":
                self._require_state(record, RuntimeState.STOPPED, RuntimeState.FAILED)
                record.state = RuntimeState.ARCHIVED

            record.last_receipt_id = action.receipt_id or record.last_receipt_id
            record.updated_at = now
            self._log(record, action.action, action.actor_id, action.reason)
            return record

    def _health_state(self, record: RuntimeRecord) -> RuntimeState:
        required = [item for item in record.dependencies if item.required]
        if any(item.health == HealthState.UNHEALTHY for item in required):
            return RuntimeState.CIRCUIT_OPEN
        if any(item.health in {HealthState.UNKNOWN, HealthState.DEGRADED} for item in required):
            return RuntimeState.DEGRADED
        return RuntimeState.HEALTHY

    def _enforce_governance(self, record: RuntimeRecord) -> None:
        if record.risk_brain_blocked:
            raise RuntimeSupervisorError("Risk Brain hard block")
        if not record.upstream_evidence_verified:
            raise RuntimeSupervisorError("upstream evidence required")
        if not record.approval_token_hash:
            raise RuntimeSupervisorError("human approval required")

    def _consume_receipt(self, receipt_id: str | None) -> None:
        if not receipt_id:
            raise RuntimeSupervisorError("receipt id required")
        if receipt_id in self._receipts:
            raise RuntimeSupervisorError("receipt replay detected")
        self._receipts.add(receipt_id)

    @staticmethod
    def _require_state(record: RuntimeRecord, *states: RuntimeState) -> None:
        if record.state not in states:
            expected = ", ".join(state.value for state in states)
            raise RuntimeSupervisorError(f"invalid state transition from {record.state.value}; expected {expected}")

    def _log(self, record: RuntimeRecord, action: str, actor_id: str, reason: str | None) -> None:
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


service = RuntimeSupervisorService()
