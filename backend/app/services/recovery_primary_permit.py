from datetime import datetime, timedelta, timezone
from hashlib import sha256
from json import dumps
from secrets import token_urlsafe
from typing import Dict, Set, Tuple
from uuid import uuid4

from app.schemas.recovery_primary_permit import *

PROTECTED = {"fund-movement", "order-submit", "trade-execute", "credential-mutate", "permission-escalate", "disable-safety-control"}


class RecoveryPrimaryPermitService:
    def __init__(self):
        self._records: Dict[Tuple[str, str], RecoveryPermitRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._ops: Set[Tuple[str, str]] = set()
        self._tokens: Dict[Tuple[str, str], str] = {}
        self._audit = []

    def status(self):
        return {
            "module": "one-time-recovery-permit-primary-handoff-governance",
            "version": "21.140",
            "external_execution_enabled": False,
            "autonomous_recovery_enabled": False,
            "single_use_permit": True,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    @staticmethod
    def _digest(value):
        return sha256(dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

    def create(self, p: RecoveryPermitCreate):
        key = (p.workspace_id, p.source_key)
        if key in self._sources:
            raise ValueError("duplicate source_key for workspace")
        blocked = p.operation in PROTECTED or p.upstream_risk_brain_blocked
        if not blocked and p.plan_state != "ready":
            raise ValueError("recovery plan must be ready")
        state = RecoveryPermitState.BLOCKED if blocked else RecoveryPermitState.PLAN_READY
        binding = self._digest({
            "recovery_plan_id": p.recovery_plan_id,
            "recovery_plan_digest": p.recovery_plan_digest,
            "recovery_readiness_digest": p.recovery_readiness_digest,
            "dispatch_plan_digest": p.dispatch_plan_digest,
            "operation": p.operation,
            "target": p.target,
            "primary_adapter_id": p.primary_adapter_id,
            "primary_worker_id": p.primary_worker_id,
            "gateway_id": p.gateway_id,
            "sandbox_policy_digest": p.sandbox_policy_digest,
            "gateway_policy_digest": p.gateway_policy_digest,
            "worker_policy_digest": p.worker_policy_digest,
        })
        r = RecoveryPermitRecord(
            permit_id=str(uuid4()), workspace_id=p.workspace_id, source_key=p.source_key, state=state,
            recovery_plan_id=p.recovery_plan_id, recovery_plan_digest=p.recovery_plan_digest,
            recovery_readiness_digest=p.recovery_readiness_digest, dispatch_plan_digest=p.dispatch_plan_digest,
            operation=p.operation, target=p.target, primary_adapter_id=p.primary_adapter_id,
            primary_worker_id=p.primary_worker_id, gateway_id=p.gateway_id,
            sandbox_policy_digest=p.sandbox_policy_digest, gateway_policy_digest=p.gateway_policy_digest,
            worker_policy_digest=p.worker_policy_digest, binding_digest=binding,
        )
        self._records[(p.workspace_id, r.permit_id)] = r
        self._sources.add(key)
        self._audit.append({"workspace_id": p.workspace_id, "permit_id": r.permit_id, "action": "create", "actor": p.requested_by, "digest": binding})
        return r

    def list(self, ws):
        return [r for (w, _), r in self._records.items() if w == ws]

    def get(self, ws, permit_id):
        if (ws, permit_id) not in self._records:
            raise KeyError("permit not found")
        return self._records[(ws, permit_id)]

    def act(self, ws, permit_id, action, actor, operation_id, reason=None):
        if (ws, operation_id) in self._ops:
            raise ValueError("operation replay detected")
        r = self.get(ws, permit_id)
        if r.state == RecoveryPermitState.BLOCKED and action not in {"revoke", "archive"}:
            raise ValueError("risk brain hard block")
        transitions = {
            "submit-review": RecoveryPermitState.REVIEW_REQUIRED,
            "approve": RecoveryPermitState.APPROVED,
            "revoke": RecoveryPermitState.REVOKED,
            "archive": RecoveryPermitState.ARCHIVED,
        }
        if action == "issue":
            if r.state != RecoveryPermitState.APPROVED:
                raise ValueError("human approval required before permit issuance")
            token = token_urlsafe(32)
            now = datetime.now(timezone.utc)
            expires = now + timedelta(seconds=300)
            r = r.model_copy(update={"state": RecoveryPermitState.ISSUED, "permit_token_digest": sha256(token.encode()).hexdigest(), "issued_at": now, "expires_at": expires, "version": r.version + 1})
            self._tokens[(ws, permit_id)] = token
            self._records[(ws, permit_id)] = r
            self._ops.add((ws, operation_id))
            self._audit.append({"workspace_id": ws, "permit_id": permit_id, "action": action, "actor": actor, "operation_id": operation_id, "reason": reason})
            return {"record": r, "permit_token": token}
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and r.state != RecoveryPermitState.REVIEW_REQUIRED:
            raise ValueError("review required before approval")
        new = transitions[action]
        r = r.model_copy(update={"state": new, "approved_by": actor if action == "approve" else r.approved_by, "version": r.version + 1})
        self._records[(ws, permit_id)] = r
        self._ops.add((ws, operation_id))
        self._audit.append({"workspace_id": ws, "permit_id": permit_id, "action": action, "actor": actor, "operation_id": operation_id, "reason": reason})
        return r

    def consume(self, permit_id: str, p: RecoveryPermitConsume):
        if (p.workspace_id, p.operation_id) in self._ops:
            raise ValueError("operation replay detected")
        r = self.get(p.workspace_id, permit_id)
        if r.state != RecoveryPermitState.ISSUED:
            raise ValueError("permit is not issued or already consumed")
        if r.expires_at and datetime.now(timezone.utc) >= r.expires_at:
            r = r.model_copy(update={"state": RecoveryPermitState.EXPIRED, "version": r.version + 1})
            self._records[(p.workspace_id, permit_id)] = r
            raise ValueError("permit expired")
        expected = self._tokens.get((p.workspace_id, permit_id))
        if not expected or p.permit_token != expected:
            raise ValueError("permit token mismatch")
        if p.recovery_plan_digest != r.recovery_plan_digest:
            raise ValueError("recovery plan digest mismatch")
        if p.primary_adapter_id != r.primary_adapter_id or p.primary_worker_id != r.primary_worker_id or p.gateway_id != r.gateway_id:
            raise ValueError("primary handoff identity mismatch")
        now = datetime.now(timezone.utc)
        r = r.model_copy(update={"state": RecoveryPermitState.CONSUMED, "consumed_at": now, "version": r.version + 1})
        self._records[(p.workspace_id, permit_id)] = r
        self._tokens.pop((p.workspace_id, permit_id), None)
        self._ops.add((p.workspace_id, p.operation_id))
        self._audit.append({"workspace_id": p.workspace_id, "permit_id": permit_id, "action": "consume", "actor": p.actor, "operation_id": p.operation_id, "binding_digest": r.binding_digest})
        return r

    def audit(self, ws):
        return [x for x in self._audit if x["workspace_id"] == ws]


recovery_primary_permit_service = RecoveryPrimaryPermitService()
