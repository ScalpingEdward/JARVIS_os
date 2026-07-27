from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.adapter_worker_execution_runtime import (
    AdapterWorkerExecutionCreate,
    AdapterWorkerHeartbeat,
    AdapterWorkerLeaseRequest,
    AdapterWorkerRecord,
    AdapterWorkerResult,
    AdapterWorkerState,
)


class AdapterWorkerExecutionRuntimeService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AdapterWorkerRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    def status(self) -> dict:
        return {
            "module": "adapter-worker-execution-lease-heartbeat-runtime",
            "version": "21.119",
            "worker_runtime_enabled": True,
            "lease_heartbeat_enabled": True,
            "external_adapter_execution_enabled": False,
            "fund_movement_enabled": False,
            "order_submission_enabled": False,
            "trading_execution_enabled": False,
            "credential_mutation_enabled": False,
            "permission_escalation_enabled": False,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AdapterWorkerExecutionCreate) -> AdapterWorkerRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._sources:
            raise ValueError("duplicate source_key for workspace")

        flags: List[str] = []
        if payload.operation in payload.protected_operations:
            flags.append("risk-brain-hard-block")
        if payload.side_effect_level == "critical":
            flags.append("critical-side-effect-review")

        state = AdapterWorkerState.BLOCKED if "risk-brain-hard-block" in flags else AdapterWorkerState.PENDING
        record = AdapterWorkerRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            gateway_record_id=payload.gateway_record_id,
            adapter_id=payload.adapter_id,
            tool_name=payload.tool_name,
            operation=payload.operation,
            state=state,
            risk_flags=sorted(set(flags)),
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._sources.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def get(self, workspace_id: str, record_id: str) -> AdapterWorkerRecord:
        key = (workspace_id, record_id)
        if key not in self._records:
            raise KeyError("record not found")
        return self._records[key]

    def list(self, workspace_id: str) -> List[AdapterWorkerRecord]:
        return [record for (ws, _), record in self._records.items() if ws == workspace_id]

    def lease(self, record_id: str, request: AdapterWorkerLeaseRequest) -> AdapterWorkerRecord:
        self._reject_replay(request.workspace_id, request.operation_id)
        record = self.get(request.workspace_id, record_id)
        if record.state != AdapterWorkerState.PENDING:
            raise ValueError("record is not leaseable")
        if record.risk_flags:
            raise ValueError("risk findings block worker lease")

        now = datetime.now(timezone.utc)
        lease_token = secrets.token_urlsafe(32)
        updated = record.model_copy(update={
            "state": AdapterWorkerState.LEASED,
            "assigned_worker_id": request.worker_id,
            "lease_token": lease_token,
            "lease_expires_at": (now + timedelta(seconds=30)).isoformat(),
            "last_heartbeat_at": now.isoformat(),
            "attempt_count": record.attempt_count + 1,
            "version": record.version + 1,
        })
        self._records[(request.workspace_id, record_id)] = updated
        self._operations.add((request.workspace_id, request.operation_id))
        self._audit_event(updated, "lease", request.worker_id, request.operation_id)
        return updated

    def heartbeat(self, record_id: str, heartbeat: AdapterWorkerHeartbeat) -> AdapterWorkerRecord:
        self._reject_replay(heartbeat.workspace_id, heartbeat.operation_id)
        record = self.get(heartbeat.workspace_id, record_id)
        if record.state not in {AdapterWorkerState.LEASED, AdapterWorkerState.RUNNING}:
            raise ValueError("record does not accept heartbeats")
        self._validate_worker_and_lease(record, heartbeat.worker_id, heartbeat.lease_token)

        now = datetime.now(timezone.utc)
        updated = record.model_copy(update={
            "state": AdapterWorkerState.RUNNING,
            "last_heartbeat_at": now.isoformat(),
            "lease_expires_at": (now + timedelta(seconds=30)).isoformat(),
            "version": record.version + 1,
        })
        self._records[(heartbeat.workspace_id, record_id)] = updated
        self._operations.add((heartbeat.workspace_id, heartbeat.operation_id))
        self._audit_event(updated, "heartbeat", heartbeat.worker_id, heartbeat.operation_id)
        return updated

    def expire_stale_lease(self, workspace_id: str, record_id: str, actor: str, operation_id: str) -> AdapterWorkerRecord:
        self._reject_replay(workspace_id, operation_id)
        record = self.get(workspace_id, record_id)
        if record.state not in {AdapterWorkerState.LEASED, AdapterWorkerState.RUNNING}:
            raise ValueError("record has no active lease")
        if not record.lease_expires_at:
            raise ValueError("record has no lease expiry")
        if datetime.fromisoformat(record.lease_expires_at) > datetime.now(timezone.utc):
            raise ValueError("lease is still active")
        updated = record.model_copy(update={
            "state": AdapterWorkerState.HEARTBEAT_MISSED,
            "version": record.version + 1,
        })
        self._records[(workspace_id, record_id)] = updated
        self._operations.add((workspace_id, operation_id))
        self._audit_event(updated, "expire-lease", actor, operation_id)
        return updated

    def ingest_result(self, record_id: str, result: AdapterWorkerResult) -> AdapterWorkerRecord:
        self._reject_replay(result.workspace_id, result.operation_id)
        record = self.get(result.workspace_id, record_id)
        if record.state not in {AdapterWorkerState.LEASED, AdapterWorkerState.RUNNING}:
            raise ValueError("result requires active leased/running state")
        self._validate_worker_and_lease(record, result.worker_id, result.lease_token)

        target_state = {
            "succeeded": AdapterWorkerState.SUCCEEDED,
            "failed": AdapterWorkerState.FAILED,
            "timed-out": AdapterWorkerState.TIMED_OUT,
        }[result.status]
        updated = record.model_copy(update={
            "state": target_state,
            "result_status": result.status,
            "result_digest": result.output_digest,
            "actual_cost": result.cost,
            "version": record.version + 1,
        })
        self._records[(result.workspace_id, record_id)] = updated
        self._operations.add((result.workspace_id, result.operation_id))
        self._audit_event(
            updated,
            "result",
            result.worker_id,
            result.operation_id,
            {"status": result.status, "duration_ms": result.duration_ms, "cost": result.cost},
        )
        return updated

    def cancel(self, workspace_id: str, record_id: str, actor: str, operation_id: str, reason: str | None = None) -> AdapterWorkerRecord:
        self._reject_replay(workspace_id, operation_id)
        record = self.get(workspace_id, record_id)
        if record.state in {AdapterWorkerState.SUCCEEDED, AdapterWorkerState.FAILED, AdapterWorkerState.TIMED_OUT, AdapterWorkerState.ARCHIVED}:
            raise ValueError("terminal record cannot be cancelled")
        updated = record.model_copy(update={"state": AdapterWorkerState.CANCELLED, "version": record.version + 1})
        self._records[(workspace_id, record_id)] = updated
        self._operations.add((workspace_id, operation_id))
        self._audit_event(updated, "cancel", actor, operation_id, {"reason": reason} if reason else {})
        return updated

    def audit(self, workspace_id: str) -> List[dict]:
        return [entry for entry in self._audit if entry["workspace_id"] == workspace_id]

    def _validate_worker_and_lease(self, record: AdapterWorkerRecord, worker_id: str, lease_token: str) -> None:
        if record.assigned_worker_id != worker_id:
            raise ValueError("worker identity mismatch")
        if not record.lease_token or not secrets.compare_digest(record.lease_token, lease_token):
            raise ValueError("lease token mismatch")

    def _reject_replay(self, workspace_id: str, operation_id: str) -> None:
        if (workspace_id, operation_id) in self._operations:
            raise ValueError("operation replay detected")

    def _audit_event(self, record: AdapterWorkerRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        digest = hashlib.sha256(f"{record.record_id}:{action}:{operation_id}".encode()).hexdigest()
        self._audit.append({
            "audit_id": str(uuid4()),
            "workspace_id": record.workspace_id,
            "record_id": record.record_id,
            "action": action,
            "actor": actor,
            "operation_id": operation_id,
            "event_digest": digest,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


adapter_worker_execution_runtime_service = AdapterWorkerExecutionRuntimeService()
