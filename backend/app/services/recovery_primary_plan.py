from hashlib import sha256
from json import dumps
from typing import Dict, Set, Tuple
from uuid import uuid4

from app.schemas.recovery_primary_plan import *

PROTECTED = {"fund-movement", "order-submit", "trade-execute", "credential-mutate", "permission-escalate", "disable-safety-control"}


class RecoveryPrimaryPlanService:
    def __init__(self):
        self._records: Dict[Tuple[str, str], RecoveryPrimaryPlanRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._ops: Set[Tuple[str, str]] = set()
        self._audit = []

    def status(self):
        return {
            "module": "recovery-to-primary-plan-governance",
            "version": "21.139",
            "external_execution_enabled": False,
            "autonomous_recovery_enabled": False,
            "one_time_authorization_issued": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    @staticmethod
    def _digest(value):
        return sha256(dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

    def create(self, p: RecoveryPrimaryPlanCreate):
        source = (p.workspace_id, p.source_key)
        if source in self._sources:
            raise ValueError("duplicate source_key for workspace")

        pc = p.preconditions
        failures = []
        if not pc.primary_available:
            failures.append("primary-unavailable")
        if not pc.primary_healthy:
            failures.append("primary-unhealthy")
        if pc.primary_latency_ms > pc.max_primary_latency_ms:
            failures.append("primary-latency-degraded")
        if pc.primary_receipt_reconciliation < pc.min_primary_receipt_reconciliation:
            failures.append("primary-receipt-reconciliation-degraded")
        if not pc.failover_path_stable:
            failures.append("failover-path-unstable")
        if not pc.no_open_side_effect_findings:
            failures.append("open-side-effect-findings")

        blocked = p.operation in PROTECTED or p.upstream_risk_brain_blocked
        state = RecoveryPrimaryPlanState.BLOCKED if blocked else RecoveryPrimaryPlanState.DRAFT

        checks = [
            pc.primary_available,
            pc.primary_healthy,
            pc.primary_latency_ms <= pc.max_primary_latency_ms,
            pc.primary_receipt_reconciliation >= pc.min_primary_receipt_reconciliation,
            pc.failover_path_stable,
            pc.no_open_side_effect_findings,
        ]
        assurance = (sum(checks) / len(checks)) * pc.confidence * pc.freshness
        rollback = min(1.0, len(p.rollback_criteria) / 6)
        validation = min(1.0, len(p.validation_checks) / 6)
        residual = min(1.0, 1.0 - assurance)
        scores = RecoveryPrimaryPlanScores(
            precondition_assurance=round(assurance, 4),
            rollback_readiness=round(rollback, 4),
            validation_readiness=round(validation, 4),
            residual_risk=round(residual, 4),
        )
        plan_digest = self._digest({
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
            "rollback_criteria": p.rollback_criteria,
            "validation_checks": p.validation_checks,
            "precondition_failures": failures,
            "scores": scores.model_dump(),
        })
        r = RecoveryPrimaryPlanRecord(
            record_id=str(uuid4()), workspace_id=p.workspace_id, source_key=p.source_key, state=state,
            recovery_readiness_id=p.recovery_readiness_id, recovery_readiness_digest=p.recovery_readiness_digest,
            dispatch_plan_id=p.dispatch_plan_id, dispatch_plan_digest=p.dispatch_plan_digest,
            operation=p.operation, target=p.target, primary_adapter_id=p.primary_adapter_id,
            primary_worker_id=p.primary_worker_id, standby_adapter_id=p.standby_adapter_id,
            standby_worker_id=p.standby_worker_id, gateway_id=p.gateway_id,
            sandbox_policy_digest=p.sandbox_policy_digest, gateway_policy_digest=p.gateway_policy_digest,
            worker_policy_digest=p.worker_policy_digest, rollback_criteria=p.rollback_criteria,
            validation_checks=p.validation_checks, precondition_failures=failures, scores=scores,
            plan_digest=plan_digest,
        )
        self._records[(p.workspace_id, r.record_id)] = r
        self._sources.add(source)
        self._audit.append({"workspace_id": p.workspace_id, "record_id": r.record_id, "action": "create", "actor": p.requested_by, "digest": plan_digest})
        return r

    def list(self, workspace_id):
        return [r for (w, _), r in self._records.items() if w == workspace_id]

    def get(self, workspace_id, record_id):
        if (workspace_id, record_id) not in self._records:
            raise KeyError("record not found")
        return self._records[(workspace_id, record_id)]

    def act(self, workspace_id, record_id, action, actor, operation_id, reason=None):
        if (workspace_id, operation_id) in self._ops:
            raise ValueError("operation replay detected")
        r = self.get(workspace_id, record_id)
        if r.state == RecoveryPrimaryPlanState.BLOCKED and action not in {"revoke", "archive"}:
            raise ValueError("risk brain hard block")

        if action == "validate-preconditions":
            if r.precondition_failures:
                raise ValueError("recovery preconditions not satisfied")
            new = RecoveryPrimaryPlanState.PRECONDITION_READY
        elif action == "submit-review":
            if r.state != RecoveryPrimaryPlanState.PRECONDITION_READY:
                raise ValueError("preconditions must be validated before review")
            new = RecoveryPrimaryPlanState.REVIEW_REQUIRED
        elif action == "approve":
            if r.state != RecoveryPrimaryPlanState.REVIEW_REQUIRED:
                raise ValueError("review required before approval")
            new = RecoveryPrimaryPlanState.APPROVED
        elif action == "mark-ready":
            if r.state != RecoveryPrimaryPlanState.APPROVED or not r.approved_by:
                raise ValueError("human approval required before ready state")
            new = RecoveryPrimaryPlanState.READY
        elif action == "revoke":
            new = RecoveryPrimaryPlanState.REVOKED
        elif action == "archive":
            new = RecoveryPrimaryPlanState.ARCHIVED
        else:
            raise ValueError("unsupported action")

        r = r.model_copy(update={
            "state": new,
            "approved_by": actor if action == "approve" else r.approved_by,
            "version": r.version + 1,
        })
        self._records[(workspace_id, record_id)] = r
        self._ops.add((workspace_id, operation_id))
        self._audit.append({"workspace_id": workspace_id, "record_id": record_id, "action": action, "actor": actor, "operation_id": operation_id, "reason": reason})
        return r

    def audit(self, workspace_id):
        return [x for x in self._audit if x["workspace_id"] == workspace_id]


recovery_primary_plan_service = RecoveryPrimaryPlanService()
