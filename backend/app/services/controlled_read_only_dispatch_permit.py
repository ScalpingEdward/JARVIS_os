from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.controlled_read_only_dispatch_permit import (
    DispatchPermitAction,
    DispatchPermitConsume,
    DispatchPermitCreate,
    DispatchPermitRecord,
    DispatchPermitState,
)


class ControlledReadOnlyDispatchPermitService:
    PROTECTED_OPERATIONS = {
        "fund-movement",
        "order-submit",
        "trade-execute",
        "credential-mutate",
        "permission-escalate",
        "safety-control-disable",
        "delete-repository",
    }

    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], DispatchPermitRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    def status(self) -> dict:
        return {
            "module": "controlled-read-only-dispatch-one-time-permit-governance",
            "version": "21.129",
            "one_time_permit_enabled": True,
            "permit_max_uses": 1,
            "permit_max_ttl_seconds": 300,
            "read_only_methods": ["GET", "HEAD"],
            "external_dispatch_executed_by_module": False,
            "fund_movement_enabled": False,
            "order_submission_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: DispatchPermitCreate) -> DispatchPermitRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._sources:
            raise ValueError("duplicate source_key for workspace")
        flags = self._risk_flags(payload)
        state = DispatchPermitState.BLOCKED if "risk-brain-hard-block" in flags else DispatchPermitState.REVIEW_REQUIRED
        record = DispatchPermitRecord(
            permit_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            authorization_chain_record_id=payload.authorization_chain_record_id,
            authorization_chain_digest=payload.authorization_chain_digest,
            operation=payload.operation,
            target=payload.target,
            method=payload.method,
            adapter_id=payload.adapter_id,
            worker_id=payload.worker_id,
            gateway_record_id=payload.gateway_record_id,
            dispatch_token_digest=payload.dispatch_token_digest,
            risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.permit_id)] = record
        self._sources.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.permit_id}")
        return record

    def list(self, workspace_id: str) -> List[DispatchPermitRecord]:
        return [record for (ws, _), record in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, permit_id: str) -> DispatchPermitRecord:
        key = (workspace_id, permit_id)
        if key not in self._records:
            raise KeyError("permit not found")
        record = self._records[key]
        return self._expire_if_needed(record)

    def act(self, permit_id: str, payload: DispatchPermitAction) -> DispatchPermitRecord:
        self._guard_replay(payload.workspace_id, payload.operation_id)
        record = self.get(payload.workspace_id, permit_id)
        if payload.action == "approve":
            if record.state != DispatchPermitState.REVIEW_REQUIRED:
                raise ValueError("review-required state required before approval")
            if record.risk_flags:
                raise ValueError("unresolved permit findings block approval")
            updated = record.model_copy(update={"state": DispatchPermitState.APPROVED, "approved_by": payload.actor, "version": record.version + 1})
        elif payload.action == "issue":
            if record.state != DispatchPermitState.APPROVED:
                raise ValueError("human approval required before permit issuance")
            now = datetime.now(timezone.utc)
            ttl = self._ttl_for(record)
            expires = now + timedelta(seconds=ttl)
            token = sha256(f"{record.permit_id}|{record.authorization_chain_digest}|{record.dispatch_token_digest}|{now.isoformat()}".encode()).hexdigest()
            updated = record.model_copy(update={
                "state": DispatchPermitState.ISSUED,
                "permit_token_digest": token,
                "issued_at": now.isoformat(),
                "expires_at": expires.isoformat(),
                "issued_by": payload.actor,
                "version": record.version + 1,
            })
        elif payload.action == "revoke":
            if record.state in {DispatchPermitState.CONSUMED, DispatchPermitState.ARCHIVED}:
                raise ValueError("terminal permit cannot be revoked")
            updated = record.model_copy(update={"state": DispatchPermitState.REVOKED, "version": record.version + 1})
        elif payload.action == "archive":
            if record.state not in {DispatchPermitState.CONSUMED, DispatchPermitState.EXPIRED, DispatchPermitState.REVOKED, DispatchPermitState.BLOCKED}:
                raise ValueError("only terminal permit may be archived")
            updated = record.model_copy(update={"state": DispatchPermitState.ARCHIVED, "version": record.version + 1})
        else:
            raise ValueError("unsupported action")
        self._records[(payload.workspace_id, permit_id)] = updated
        self._operations.add((payload.workspace_id, payload.operation_id))
        self._audit_event(updated, payload.action, payload.actor, payload.operation_id, payload.reason)
        return updated

    def consume(self, permit_id: str, payload: DispatchPermitConsume) -> DispatchPermitRecord:
        self._guard_replay(payload.workspace_id, payload.operation_id)
        record = self.get(payload.workspace_id, permit_id)
        if record.state != DispatchPermitState.ISSUED:
            raise ValueError("issued permit required")
        if payload.permit_token_digest != record.permit_token_digest:
            raise ValueError("permit token mismatch")
        if payload.authorization_chain_digest != record.authorization_chain_digest:
            raise ValueError("authorization chain digest mismatch")
        if payload.dispatch_token_digest != record.dispatch_token_digest:
            raise ValueError("dispatch token mismatch")
        if payload.adapter_id != record.adapter_id or payload.worker_id != record.worker_id:
            raise ValueError("adapter/worker binding mismatch")
        now = datetime.now(timezone.utc)
        updated = record.model_copy(update={
            "state": DispatchPermitState.CONSUMED,
            "consumed_at": now.isoformat(),
            "consumed_by": payload.actor,
            "version": record.version + 1,
        })
        self._records[(payload.workspace_id, permit_id)] = updated
        self._operations.add((payload.workspace_id, payload.operation_id))
        self._audit_event(updated, "consume", payload.actor, payload.operation_id)
        return updated

    def audit(self, workspace_id: str) -> List[dict]:
        return [event for event in self._audit if event["workspace_id"] == workspace_id]

    def _risk_flags(self, payload: DispatchPermitCreate) -> List[str]:
        flags: List[str] = []
        if payload.authorization_chain_state != "eligible":
            flags += ["authorization-chain-not-eligible", "risk-brain-hard-block"]
        if payload.risk_brain_hard_blocked:
            flags += ["upstream-risk-brain-hard-block", "risk-brain-hard-block"]
        if payload.operation in self.PROTECTED_OPERATIONS:
            flags += [f"protected-operation:{payload.operation}", "risk-brain-hard-block"]
        if payload.method not in {"GET", "HEAD"}:
            flags += ["write-method-detected", "risk-brain-hard-block"]
        return sorted(set(flags))

    @staticmethod
    def _ttl_for(record: DispatchPermitRecord) -> int:
        # Fixed conservative issuance window; schema caps requested policy at 300 seconds.
        return 120

    def _expire_if_needed(self, record: DispatchPermitRecord) -> DispatchPermitRecord:
        if record.state == DispatchPermitState.ISSUED and record.expires_at:
            expires = datetime.fromisoformat(record.expires_at)
            if datetime.now(timezone.utc) >= expires:
                expired = record.model_copy(update={"state": DispatchPermitState.EXPIRED, "version": record.version + 1})
                self._records[(record.workspace_id, record.permit_id)] = expired
                self._audit_event(expired, "expire", "system", f"expire:{record.permit_id}")
                return expired
        return record

    def _guard_replay(self, workspace_id: str, operation_id: str) -> None:
        if (workspace_id, operation_id) in self._operations:
            raise ValueError("operation replay detected")

    def _audit_event(self, record: DispatchPermitRecord, action: str, actor: str, operation_id: str, detail: str | None = None) -> None:
        raw = f"{record.workspace_id}|{record.permit_id}|{action}|{actor}|{operation_id}|{record.version}"
        self._audit.append({
            "workspace_id": record.workspace_id,
            "permit_id": record.permit_id,
            "action": action,
            "actor": actor,
            "operation_id": operation_id,
            "detail": detail,
            "event_digest": sha256(raw.encode()).hexdigest(),
        })


controlled_read_only_dispatch_permit_service = ControlledReadOnlyDispatchPermitService()
