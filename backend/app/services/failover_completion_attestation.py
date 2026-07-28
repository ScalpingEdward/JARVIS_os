from hashlib import sha256
from json import dumps
from typing import Dict, Set, Tuple
from uuid import uuid4

from app.schemas.failover_completion_attestation import *

PROTECTED = {"fund-movement", "order-submit", "trade-execute", "credential-mutate", "permission-escalate", "disable-safety-control"}


class FailoverCompletionAttestationService:
    def __init__(self):
        self._records: Dict[Tuple[str, str], FailoverCompletionRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._ops: Set[Tuple[str, str]] = set()
        self._audit = []

    def status(self):
        return {
            "module": "governed-standby-dispatch-reconciliation-failover-completion-attestation",
            "version": "21.137",
            "external_execution_enabled": False,
            "autonomous_failover_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    @staticmethod
    def _digest(value):
        return sha256(dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

    def create(self, p: FailoverCompletionCreate):
        key = (p.workspace_id, p.source_key)
        if key in self._sources:
            raise ValueError("duplicate source_key for workspace")
        r = p.receipt
        protected = p.operation in PROTECTED or p.upstream_risk_brain_blocked
        binding_ok = all([
            p.permit_consumed,
            r.method.upper() in {"GET", "HEAD"},
            r.adapter_id == p.standby_adapter_id,
            r.worker_id == p.standby_worker_id,
            r.gateway_id == p.gateway_id,
            r.operation == p.operation,
            r.target == p.target,
        ])
        side_effect_safe = not any([
            r.write_side_effect_detected,
            r.credential_mutation_detected,
            r.permission_mutation_detected,
            r.fund_movement_detected,
            r.order_submission_detected,
            r.trading_execution_detected,
        ])
        state = FailoverCompletionState.BLOCKED if protected else (
            FailoverCompletionState.EVIDENCE_READY if binding_ok and side_effect_safe else FailoverCompletionState.MISMATCH
        )
        reconciliation_digest = self._digest({
            "permit": p.failover_permit_digest,
            "authorization": p.failover_authorization_digest,
            "plan": p.dispatch_plan_digest,
            "adapter": p.standby_adapter_id,
            "worker": p.standby_worker_id,
            "gateway": p.gateway_id,
            "operation": p.operation,
            "target": p.target,
            "receipt": r.receipt_digest,
            "response": r.response_digest,
            "binding_ok": binding_ok,
            "side_effect_safe": side_effect_safe,
        })
        rec = FailoverCompletionRecord(
            record_id=str(uuid4()), workspace_id=p.workspace_id, source_key=p.source_key, state=state,
            failover_permit_id=p.failover_permit_id, failover_permit_digest=p.failover_permit_digest,
            failover_authorization_id=p.failover_authorization_id, failover_authorization_digest=p.failover_authorization_digest,
            dispatch_plan_id=p.dispatch_plan_id, dispatch_plan_digest=p.dispatch_plan_digest,
            standby_adapter_id=p.standby_adapter_id, standby_worker_id=p.standby_worker_id, gateway_id=p.gateway_id,
            operation=p.operation, target=p.target, receipt_digest=r.receipt_digest, response_digest=r.response_digest,
            reconciliation_digest=reconciliation_digest, side_effect_safe=side_effect_safe, bindings_valid=binding_ok,
        )
        self._records[(p.workspace_id, rec.record_id)] = rec
        self._sources.add(key)
        self._audit.append({"workspace_id": p.workspace_id, "record_id": rec.record_id, "action": "create", "actor": p.requested_by, "digest": reconciliation_digest})
        return rec

    def list(self, workspace_id):
        return [r for (w, _), r in self._records.items() if w == workspace_id]

    def get(self, workspace_id, record_id):
        if (workspace_id, record_id) not in self._records:
            raise KeyError("record not found")
        return self._records[(workspace_id, record_id)]

    def act(self, workspace_id, record_id, action, actor, operation_id, reason=None):
        if (workspace_id, operation_id) in self._ops:
            raise ValueError("operation replay detected")
        rec = self.get(workspace_id, record_id)
        if rec.state == FailoverCompletionState.BLOCKED and action not in {"revoke", "archive"}:
            raise ValueError("risk brain hard block")
        transitions = {
            "reconcile": FailoverCompletionState.RECONCILED,
            "submit-review": FailoverCompletionState.REVIEW_REQUIRED,
            "approve": FailoverCompletionState.APPROVED,
            "attest": FailoverCompletionState.ATTESTED,
            "revoke": FailoverCompletionState.REVOKED,
            "archive": FailoverCompletionState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "reconcile" and (not rec.bindings_valid or not rec.side_effect_safe):
            raise ValueError("failover reconciliation mismatch")
        if action == "attest":
            if rec.state != FailoverCompletionState.APPROVED:
                raise ValueError("human approval required before failover attestation")
            if not rec.bindings_valid or not rec.side_effect_safe:
                raise ValueError("unsafe failover outcome cannot be attested")
        new_state = transitions[action]
        rec = rec.model_copy(update={
            "state": new_state,
            "approved_by": actor if action == "approve" else rec.approved_by,
            "version": rec.version + 1,
        })
        self._records[(workspace_id, record_id)] = rec
        self._ops.add((workspace_id, operation_id))
        self._audit.append({"workspace_id": workspace_id, "record_id": record_id, "action": action, "actor": actor, "operation_id": operation_id, "reason": reason})
        return rec

    def audit(self, workspace_id):
        return [x for x in self._audit if x["workspace_id"] == workspace_id]


failover_completion_attestation_service = FailoverCompletionAttestationService()
