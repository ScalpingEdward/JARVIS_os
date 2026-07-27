from datetime import datetime, timedelta, timezone
from hashlib import sha256
from json import dumps
from typing import Dict, Set, Tuple
from uuid import uuid4

from app.schemas.failover_permit_handoff import *


PROTECTED = {
    "fund-movement",
    "order-submit",
    "trade-execute",
    "credential-mutate",
    "permission-escalate",
    "disable-safety-control",
}


class FailoverPermitHandoffService:
    def __init__(self):
        self._records: Dict[Tuple[str, str], FailoverPermitRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._ops: Set[Tuple[str, str]] = set()
        self._audit = []

    def status(self):
        return {
            "module": "one-time-failover-permit-standby-handoff-governance",
            "version": "21.136",
            "external_execution_enabled": False,
            "autonomous_failover_enabled": False,
            "single_use_permits": True,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    @staticmethod
    def _digest(value):
        return sha256(dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def create(self, payload: FailoverPermitCreate):
        key = (payload.workspace_id, payload.source_key)
        if key in self._sources:
            raise ValueError("duplicate source_key for workspace")

        blocked = (
            payload.operation in PROTECTED
            or payload.upstream_risk_brain_blocked
            or not payload.failover_authorized
        )
        state = FailoverPermitState.BLOCKED if blocked else FailoverPermitState.AUTHORIZED
        handoff_digest = self._digest(
            {
                "authorization": payload.failover_authorization_digest,
                "plan": payload.dispatch_plan_digest,
                "operation": payload.operation,
                "target": payload.target,
                "standby_adapter": payload.standby_adapter_id,
                "standby_worker": payload.standby_worker_id,
                "gateway": payload.gateway_id,
                "sandbox_policy": payload.sandbox_policy_digest,
                "gateway_policy": payload.gateway_policy_digest,
                "worker_policy": payload.worker_policy_digest,
            }
        )
        record = FailoverPermitRecord(
            permit_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            failover_authorization_id=payload.failover_authorization_id,
            failover_authorization_digest=payload.failover_authorization_digest,
            dispatch_plan_id=payload.dispatch_plan_id,
            dispatch_plan_digest=payload.dispatch_plan_digest,
            operation=payload.operation,
            target=payload.target,
            standby_adapter_id=payload.standby_adapter_id,
            standby_worker_id=payload.standby_worker_id,
            gateway_id=payload.gateway_id,
            sandbox_policy_digest=payload.sandbox_policy_digest,
            gateway_policy_digest=payload.gateway_policy_digest,
            worker_policy_digest=payload.worker_policy_digest,
            handoff_digest=handoff_digest,
        )
        self._records[(payload.workspace_id, record.permit_id)] = record
        self._sources.add(key)
        self._audit.append({
            "workspace_id": payload.workspace_id,
            "permit_id": record.permit_id,
            "action": "create",
            "actor": payload.requested_by,
            "digest": handoff_digest,
        })
        return record

    def list(self, workspace_id):
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id, permit_id):
        if (workspace_id, permit_id) not in self._records:
            raise KeyError("permit not found")
        return self._records[(workspace_id, permit_id)]

    def act(self, workspace_id, permit_id, action, actor, operation_id, reason=None):
        if (workspace_id, operation_id) in self._ops:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, permit_id)
        if record.state == FailoverPermitState.BLOCKED and action not in {"revoke", "archive"}:
            raise ValueError("risk brain hard block")

        if action == "submit-review":
            new_state = FailoverPermitState.REVIEW_REQUIRED
        elif action == "approve":
            if record.state != FailoverPermitState.REVIEW_REQUIRED:
                raise ValueError("review required before approval")
            new_state = FailoverPermitState.APPROVED
        elif action == "issue":
            if record.state != FailoverPermitState.APPROVED:
                raise ValueError("human approval required before permit issuance")
            now = self._now()
            token_digest = self._digest({
                "permit_id": record.permit_id,
                "authorization": record.failover_authorization_digest,
                "handoff": record.handoff_digest,
                "issued_at": now.isoformat(),
            })
            updated = record.model_copy(update={
                "state": FailoverPermitState.ISSUED,
                "issued_at": now.isoformat(),
                "expires_at": (now + timedelta(seconds=120)).isoformat(),
                "permit_token_digest": token_digest,
                "version": record.version + 1,
            })
            self._records[(workspace_id, permit_id)] = updated
            self._ops.add((workspace_id, operation_id))
            self._audit.append({"workspace_id": workspace_id, "permit_id": permit_id, "action": action, "actor": actor, "operation_id": operation_id, "reason": reason, "digest": token_digest})
            return updated
        elif action == "revoke":
            new_state = FailoverPermitState.REVOKED
        elif action == "archive":
            new_state = FailoverPermitState.ARCHIVED
        else:
            raise ValueError("unsupported action")

        updated = record.model_copy(update={
            "state": new_state,
            "approved_by": actor if action == "approve" else record.approved_by,
            "version": record.version + 1,
        })
        self._records[(workspace_id, permit_id)] = updated
        self._ops.add((workspace_id, operation_id))
        self._audit.append({"workspace_id": workspace_id, "permit_id": permit_id, "action": action, "actor": actor, "operation_id": operation_id, "reason": reason})
        return updated

    def consume(self, permit_id: str, payload: FailoverPermitConsume):
        if (payload.workspace_id, payload.operation_id) in self._ops:
            raise ValueError("operation replay detected")
        record = self.get(payload.workspace_id, permit_id)
        if record.state != FailoverPermitState.ISSUED:
            raise ValueError("permit is not issued")
        if not record.expires_at or datetime.fromisoformat(record.expires_at) <= self._now():
            expired = record.model_copy(update={"state": FailoverPermitState.EXPIRED, "version": record.version + 1})
            self._records[(payload.workspace_id, permit_id)] = expired
            raise ValueError("permit expired")
        if payload.failover_authorization_digest != record.failover_authorization_digest:
            raise ValueError("failover authorization binding mismatch")
        if payload.standby_adapter_id != record.standby_adapter_id:
            raise ValueError("standby adapter binding mismatch")
        if payload.standby_worker_id != record.standby_worker_id:
            raise ValueError("standby worker binding mismatch")
        if payload.gateway_id != record.gateway_id:
            raise ValueError("gateway binding mismatch")

        now = self._now().isoformat()
        updated = record.model_copy(update={
            "state": FailoverPermitState.CONSUMED,
            "consumed_at": now,
            "version": record.version + 1,
        })
        self._records[(payload.workspace_id, permit_id)] = updated
        self._ops.add((payload.workspace_id, payload.operation_id))
        self._audit.append({
            "workspace_id": payload.workspace_id,
            "permit_id": permit_id,
            "action": "consume",
            "actor": payload.actor,
            "operation_id": payload.operation_id,
            "digest": self._digest({"permit": record.permit_token_digest, "consumed_at": now}),
        })
        return updated

    def audit(self, workspace_id):
        return [entry for entry in self._audit if entry["workspace_id"] == workspace_id]


failover_permit_handoff_service = FailoverPermitHandoffService()
