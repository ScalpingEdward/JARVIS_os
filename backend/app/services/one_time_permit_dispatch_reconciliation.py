from __future__ import annotations

import hashlib
import json
from typing import Dict, Set, Tuple
from uuid import uuid4

from app.schemas.one_time_permit_dispatch_reconciliation import (
    DispatchHandoffCreate,
    DispatchReceipt,
    DispatchReconciliationRecord,
    DispatchReconciliationState,
)


PROTECTED_OPERATIONS = {
    "fund-movement",
    "order-submit",
    "trade-execute",
    "credential-mutate",
    "permission-escalate",
    "disable-safety-control",
}


class OneTimePermitDispatchReconciliationService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], DispatchReconciliationRecord] = {}
        self._payloads: Dict[Tuple[str, str], DispatchHandoffCreate] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._ops: Set[Tuple[str, str]] = set()
        self._consumed_permits: Set[Tuple[str, str]] = set()
        self._audit: list[dict] = []

    @staticmethod
    def _digest(payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def status(self) -> dict:
        return {
            "module": "one-time-permit-dispatch-handoff-receipt-reconciliation",
            "version": "21.130",
            "read_only_only": True,
            "permit_single_use": True,
            "receipt_reconciliation_required": True,
            "direct_network_client_enabled": False,
            "fund_movement_enabled": False,
            "order_submission_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: DispatchHandoffCreate) -> DispatchReconciliationRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._sources:
            raise ValueError("duplicate source_key for workspace")

        flags: list[str] = []
        method = payload.method.upper()
        if method not in {"GET", "HEAD"}:
            flags.append("risk-brain-hard-block")
            flags.append("write-method-prohibited")
        if payload.operation.lower() in PROTECTED_OPERATIONS:
            flags.append("risk-brain-hard-block")
            flags.append("protected-operation")
        if payload.upstream_risk_brain_blocked:
            flags.append("risk-brain-hard-block")
            flags.append("upstream-risk-brain-block")
        if not payload.permit_eligible or not payload.permit_issued:
            flags.append("permit-not-eligible-or-issued")
        if payload.permit_expired:
            flags.append("permit-expired")
        if not payload.human_approved:
            flags.append("human-approval-missing")

        handoff_digest = self._digest(
            {
                "workspace_id": payload.workspace_id,
                "permit_id": payload.permit_id,
                "permit_token_digest": payload.permit_token_digest,
                "authorization_chain_record_id": payload.authorization_chain_record_id,
                "authorization_chain_digest": payload.authorization_chain_digest,
                "gateway_record_id": payload.gateway_record_id,
                "gateway_dispatch_token_digest": payload.gateway_dispatch_token_digest,
                "worker_record_id": payload.worker_record_id,
                "adapter_id": payload.adapter_id,
                "operation": payload.operation,
                "target": payload.target,
                "method": method,
            }
        )

        state = (
            DispatchReconciliationState.BLOCKED
            if "risk-brain-hard-block" in flags
            else DispatchReconciliationState.REVIEW_REQUIRED
        )
        record = DispatchReconciliationRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            permit_id=payload.permit_id,
            authorization_chain_record_id=payload.authorization_chain_record_id,
            gateway_record_id=payload.gateway_record_id,
            worker_record_id=payload.worker_record_id,
            adapter_id=payload.adapter_id,
            operation=payload.operation,
            target=payload.target,
            handoff_digest=handoff_digest,
            risk_flags=sorted(set(flags)),
        )
        key = (payload.workspace_id, record.record_id)
        self._records[key] = record
        self._payloads[key] = payload
        self._sources.add(source)
        self._audit_event(payload.workspace_id, record.record_id, "create", payload.requested_by)
        return record

    def list(self, workspace_id: str) -> list[DispatchReconciliationRecord]:
        return [r for (ws, _), r in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> DispatchReconciliationRecord:
        key = (workspace_id, record_id)
        if key not in self._records:
            raise KeyError("record not found")
        return self._records[key]

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> DispatchReconciliationRecord:
        if (workspace_id, operation_id) in self._ops:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        payload = self._payloads[(workspace_id, record_id)]

        if "risk-brain-hard-block" in record.risk_flags and action not in {"revoke", "archive"}:
            raise ValueError("risk brain hard block is authoritative")

        if action == "approve":
            unresolved = [f for f in record.risk_flags if f not in {"human-approval-missing"}]
            if unresolved:
                raise ValueError("unresolved dispatch findings block approval")
            if not payload.human_approved:
                raise ValueError("human approval evidence required")
            record = record.model_copy(update={"state": DispatchReconciliationState.APPROVED, "approved_by": actor, "risk_flags": [], "version": record.version + 1})
        elif action == "prepare-handoff":
            if record.state != DispatchReconciliationState.APPROVED:
                raise ValueError("approval required before handoff")
            record = record.model_copy(update={"state": DispatchReconciliationState.HANDOFF_READY, "version": record.version + 1})
        elif action == "consume-permit":
            if record.state != DispatchReconciliationState.HANDOFF_READY:
                raise ValueError("handoff-ready state required before permit consumption")
            permit_key = (workspace_id, payload.permit_id)
            if permit_key in self._consumed_permits:
                raise ValueError("permit already consumed")
            if payload.permit_expired:
                raise ValueError("permit expired")
            self._consumed_permits.add(permit_key)
            record = record.model_copy(update={"state": DispatchReconciliationState.PERMIT_CONSUMED, "version": record.version + 1})
        elif action == "mark-dispatched":
            if record.state != DispatchReconciliationState.PERMIT_CONSUMED:
                raise ValueError("single-use permit must be consumed before dispatch handoff")
            record = record.model_copy(update={"state": DispatchReconciliationState.DISPATCHED, "version": record.version + 1})
        elif action == "fail":
            record = record.model_copy(update={"state": DispatchReconciliationState.FAILED, "version": record.version + 1})
        elif action == "revoke":
            record = record.model_copy(update={"state": DispatchReconciliationState.REVOKED, "version": record.version + 1})
        elif action == "archive":
            record = record.model_copy(update={"state": DispatchReconciliationState.ARCHIVED, "version": record.version + 1})
        else:
            raise ValueError("unsupported action")

        self._records[(workspace_id, record_id)] = record
        self._ops.add((workspace_id, operation_id))
        self._audit_event(workspace_id, record_id, action, actor, operation_id, reason)
        return record

    def reconcile(self, record_id: str, receipt: DispatchReceipt) -> DispatchReconciliationRecord:
        record = self.get(receipt.workspace_id, record_id)
        payload = self._payloads[(receipt.workspace_id, record_id)]
        if record.state != DispatchReconciliationState.DISPATCHED:
            raise ValueError("record must be dispatched before receipt reconciliation")

        mismatches: list[str] = []
        checks = {
            "permit_id": (receipt.permit_id, payload.permit_id),
            "permit_token_digest": (receipt.permit_token_digest, payload.permit_token_digest),
            "authorization_chain_digest": (receipt.authorization_chain_digest, payload.authorization_chain_digest),
            "gateway_dispatch_token_digest": (receipt.gateway_dispatch_token_digest, payload.gateway_dispatch_token_digest),
            "worker_record_id": (receipt.worker_record_id, payload.worker_record_id),
            "adapter_id": (receipt.adapter_id, payload.adapter_id),
            "operation": (receipt.operation, payload.operation),
            "target": (receipt.target, payload.target),
        }
        for name, (actual, expected) in checks.items():
            if actual != expected:
                mismatches.append(name)

        reconciliation_digest = self._digest(
            {
                "handoff_digest": record.handoff_digest,
                "response_digest": receipt.response_digest,
                "receipt_digest": receipt.receipt_digest,
                "duration_ms": receipt.duration_ms,
                "response_bytes": receipt.response_bytes,
                "status_code": receipt.status_code,
                "mismatches": sorted(mismatches),
            }
        )
        state = DispatchReconciliationState.MISMATCH if mismatches else DispatchReconciliationState.RECONCILED
        flags = list(record.risk_flags)
        if mismatches:
            flags.extend(["receipt-binding-mismatch", "risk-brain-review-required"])

        record = record.model_copy(
            update={
                "state": state,
                "reconciliation_digest": reconciliation_digest,
                "response_digest": receipt.response_digest,
                "receipt_digest": receipt.receipt_digest,
                "mismatch_reasons": sorted(mismatches),
                "risk_flags": sorted(set(flags)),
                "version": record.version + 1,
            }
        )
        self._records[(receipt.workspace_id, record_id)] = record
        self._audit_event(receipt.workspace_id, record_id, "reconcile-receipt", "worker-receipt")
        return record

    def audit(self, workspace_id: str) -> list[dict]:
        return [event for event in self._audit if event["workspace_id"] == workspace_id]

    def _audit_event(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str | None = None, reason: str | None = None) -> None:
        event = {"workspace_id": workspace_id, "record_id": record_id, "action": action, "actor": actor, "operation_id": operation_id, "reason": reason}
        event["event_digest"] = self._digest(event)
        self._audit.append(event)


one_time_permit_dispatch_reconciliation_service = OneTimePermitDispatchReconciliationService()
