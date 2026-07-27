from __future__ import annotations

from hashlib import sha256
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.read_only_external_adapter_executor import (
    ReadOnlyExecutionAction,
    ReadOnlyExecutionCreate,
    ReadOnlyExecutionRecord,
    ReadOnlyExecutionResult,
    ReadOnlyExecutionScores,
    ReadOnlyExecutorState,
)


class ReadOnlyExternalAdapterExecutorService:
    PROTECTED_OPERATIONS = {
        "fund-movement", "order-submit", "trade-execute", "credential-mutate",
        "permission-escalate", "safety-control-disable", "delete-repository",
    }

    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], ReadOnlyExecutionRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    def status(self) -> dict:
        return {
            "module": "read-only-external-adapter-executor",
            "version": "21.120",
            "read_only_external_execution_enabled": True,
            "write_methods_enabled": False,
            "fund_movement_enabled": False,
            "order_submission_enabled": False,
            "trading_execution_enabled": False,
            "credential_mutation_enabled": False,
            "host_pinning_required": True,
            "egress_allow_list_required": True,
            "response_size_limit_required": True,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: ReadOnlyExecutionCreate) -> ReadOnlyExecutionRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._sources:
            raise ValueError("duplicate source_key for workspace")
        flags = self._risk_flags(payload)
        residual = min(1.0, 0.05 + (0.1 if payload.request.follow_redirects else 0.0) + (0.15 if payload.request.max_response_bytes > 2_097_152 else 0.0))
        scores = ReadOnlyExecutionScores(
            egress_assurance=1.0,
            host_pinning_assurance=1.0,
            response_limit_assurance=1.0 if payload.request.max_response_bytes <= 2_097_152 else 0.7,
            read_only_assurance=1.0 if payload.request.method in {"GET", "HEAD"} and payload.request.side_effect_level == "read-only" else 0.0,
            residual_risk=round(residual, 4),
        )
        state = ReadOnlyExecutorState.BLOCKED if "risk-brain-hard-block" in flags else ReadOnlyExecutorState.REVIEW_REQUIRED
        record = ReadOnlyExecutionRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=state, request=payload.request, scores=scores, risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._sources.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[ReadOnlyExecutionRecord]:
        return [record for (ws, _), record in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> ReadOnlyExecutionRecord:
        if (workspace_id, record_id) not in self._records:
            raise KeyError("record not found")
        return self._records[(workspace_id, record_id)]

    def act(self, record_id: str, payload: ReadOnlyExecutionAction) -> ReadOnlyExecutionRecord:
        op = (payload.workspace_id, payload.operation_id)
        if op in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(payload.workspace_id, record_id)
        transitions = {
            "approve": ReadOnlyExecutorState.APPROVED,
            "authorize": ReadOnlyExecutorState.AUTHORIZED,
            "prepare": ReadOnlyExecutorState.READY,
            "start": ReadOnlyExecutorState.RUNNING,
            "cancel": ReadOnlyExecutorState.CANCELLED,
            "revoke": ReadOnlyExecutorState.REVOKED,
            "archive": ReadOnlyExecutorState.ARCHIVED,
        }
        if payload.action not in transitions:
            raise ValueError("unsupported action")
        if payload.action == "approve" and record.risk_flags:
            raise ValueError("unresolved executor findings block approval")
        if payload.action == "authorize" and record.state != ReadOnlyExecutorState.APPROVED:
            raise ValueError("human approval required before authorization")
        if payload.action == "prepare" and record.state != ReadOnlyExecutorState.AUTHORIZED:
            raise ValueError("authorization required before prepare")
        if payload.action == "start" and record.state != ReadOnlyExecutorState.READY:
            raise ValueError("ready state required before start")
        updated = record.model_copy(update={
            "state": transitions[payload.action],
            "approved_by": payload.actor if payload.action == "approve" else record.approved_by,
            "authorized_by": payload.actor if payload.action == "authorize" else record.authorized_by,
            "version": record.version + 1,
        })
        self._records[(payload.workspace_id, record_id)] = updated
        self._operations.add(op)
        self._audit_event(updated, payload.action, payload.actor, payload.operation_id, payload.reason)
        return updated

    def ingest_result(self, record_id: str, result: ReadOnlyExecutionResult) -> ReadOnlyExecutionRecord:
        op = (result.workspace_id, result.operation_id)
        if op in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(result.workspace_id, record_id)
        if record.state != ReadOnlyExecutorState.RUNNING:
            raise ValueError("result requires running state")
        if result.worker_id != record.request.worker_id or result.adapter_id != record.request.adapter_id:
            raise ValueError("worker/adapter binding mismatch")
        if result.response_bytes > record.request.max_response_bytes:
            raise ValueError("response exceeds configured size limit")
        state = {
            "succeeded": ReadOnlyExecutorState.SUCCEEDED,
            "failed": ReadOnlyExecutorState.FAILED,
            "timed-out": ReadOnlyExecutorState.TIMED_OUT,
        }[result.status]
        receipt_digest = sha256(
            f"{record.record_id}|{result.operation_id}|{result.status}|{result.response_digest}|{result.response_bytes}|{result.duration_ms}".encode()
        ).hexdigest()
        updated = record.model_copy(update={
            "state": state,
            "response_digest": result.response_digest,
            "response_bytes": result.response_bytes,
            "receipt_digest": receipt_digest,
            "version": record.version + 1,
        })
        self._records[(result.workspace_id, record_id)] = updated
        self._operations.add(op)
        self._audit_event(updated, "result", result.worker_id, result.operation_id, result.status)
        return updated

    def audit(self, workspace_id: str) -> List[dict]:
        return [event for event in self._audit if event["workspace_id"] == workspace_id]

    def _risk_flags(self, payload: ReadOnlyExecutionCreate) -> List[str]:
        flags: List[str] = []
        request = payload.request
        if request.operation in self.PROTECTED_OPERATIONS:
            flags += [f"protected-operation:{request.operation}", "risk-brain-hard-block"]
        if request.method not in {"GET", "HEAD"} or request.side_effect_level != "read-only":
            flags += ["write-capability-detected", "risk-brain-hard-block"]
        if request.target_host not in payload.egress_allow_hosts or request.target_host not in payload.pinned_hosts:
            flags += ["egress-policy-breach", "risk-brain-hard-block"]
        if request.follow_redirects:
            flags.append("redirect-review-required")
        return sorted(set(flags))

    def _audit_event(self, record: ReadOnlyExecutionRecord, action: str, actor: str, operation_id: str, detail: str | None = None) -> None:
        raw = f"{record.workspace_id}|{record.record_id}|{action}|{actor}|{operation_id}|{record.version}"
        self._audit.append({
            "workspace_id": record.workspace_id,
            "record_id": record.record_id,
            "action": action,
            "actor": actor,
            "operation_id": operation_id,
            "detail": detail,
            "event_digest": sha256(raw.encode()).hexdigest(),
        })


read_only_external_adapter_executor_service = ReadOnlyExternalAdapterExecutorService()
