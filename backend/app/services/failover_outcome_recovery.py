from hashlib import sha256
from json import dumps
from typing import Dict, Set, Tuple
from uuid import uuid4

from app.schemas.failover_outcome_recovery import *

PROTECTED={"fund-movement","order-submit","trade-execute","credential-mutate","permission-escalate","disable-safety-control"}


class FailoverOutcomeRecoveryService:
    def __init__(self):
        self._records: Dict[Tuple[str,str], FailoverRecoveryRecord] = {}
        self._sources: Set[Tuple[str,str]] = set()
        self._ops: Set[Tuple[str,str]] = set()
        self._audit = []

    def status(self):
        return {
            "module":"failover-outcome-trust-feedback-recovery-primary-readiness-governance",
            "version":"21.138",
            "autonomous_route_mutation_enabled":False,
            "autonomous_recovery_enabled":False,
            "external_execution_enabled":False,
            "human_approval_required":True,
            "risk_brain_authoritative":True,
        }

    @staticmethod
    def _digest(v):
        return sha256(dumps(v, sort_keys=True, separators=(",",":"), default=str).encode()).hexdigest()

    def create(self, p: FailoverRecoveryCreate):
        key=(p.workspace_id,p.source_key)
        if key in self._sources:
            raise ValueError("duplicate source_key for workspace")

        blocked = p.operation in PROTECTED or p.upstream_risk_brain_blocked
        e=p.evidence
        findings=[]
        recommendations=[]

        if not e.completion_attested: findings.append("failover-completion-not-attested")
        if not e.side_effect_safe: findings.append("side-effect-safety-failed")
        if not e.receipt_reconciled: findings.append("receipt-reconciliation-failed")
        if not e.standby_stable: findings.append("standby-not-stable")
        if not e.primary_available: findings.append("primary-unavailable")
        if e.primary_latency_ms > p.max_primary_latency_ms: findings.append("primary-latency-degraded")
        if e.primary_health < p.min_primary_health: findings.append("primary-health-below-threshold")
        if e.primary_receipt_reconciliation < p.min_primary_receipt_reconciliation: findings.append("primary-reconciliation-below-threshold")

        failover_trust = sum([
            e.completion_attested,
            e.side_effect_safe,
            e.receipt_reconciled,
            e.standby_stable,
        ]) / 4
        failover_trust *= e.confidence * e.freshness

        recovery_base = sum([
            e.primary_available,
            e.primary_latency_ms <= p.max_primary_latency_ms,
            e.primary_health >= p.min_primary_health,
            e.primary_receipt_reconciliation >= p.min_primary_receipt_reconciliation,
        ]) / 4
        recovery = recovery_base * e.confidence * e.freshness

        if failover_trust < .9:
            recommendations.append("hold-recovery-until-failover-trust-improves")
        if recovery < .9:
            recommendations.append("continue-standby-and-reassess-primary")
        if failover_trust >= .9 and recovery >= .9:
            recommendations.append("eligible-for-human-reviewed-recovery-plan")

        residual=max(0.0,1-min(failover_trust,recovery))
        scores=FailoverRecoveryScores(
            failover_trust=round(failover_trust,4),
            primary_recovery_readiness=round(recovery,4),
            residual_risk=round(residual,4),
        )
        state=FailoverRecoveryState.BLOCKED if blocked else FailoverRecoveryState.EVIDENCE_READY
        evidence_digest=self._digest(e.model_dump())
        recovery_digest=self._digest({
            "attestation":p.failover_attestation_digest,
            "dispatch_plan":p.dispatch_plan_digest,
            "operation":p.operation,
            "target":p.target,
            "scores":scores.model_dump(),
            "findings":findings,
            "recommendations":recommendations,
        })
        r=FailoverRecoveryRecord(
            record_id=str(uuid4()),workspace_id=p.workspace_id,source_key=p.source_key,state=state,
            failover_attestation_id=p.failover_attestation_id,failover_attestation_digest=p.failover_attestation_digest,
            dispatch_plan_id=p.dispatch_plan_id,dispatch_plan_digest=p.dispatch_plan_digest,operation=p.operation,target=p.target,
            primary_adapter_id=p.primary_adapter_id,primary_worker_id=p.primary_worker_id,
            standby_adapter_id=p.standby_adapter_id,standby_worker_id=p.standby_worker_id,
            findings=findings,recommendations=recommendations,scores=scores,
            evidence_digest=evidence_digest,recovery_digest=recovery_digest,
        )
        self._records[(p.workspace_id,r.record_id)]=r
        self._sources.add(key)
        self._audit.append({"workspace_id":p.workspace_id,"record_id":r.record_id,"action":"create","actor":p.requested_by,"digest":recovery_digest})
        return r

    def list(self, ws):
        return [r for (w,_),r in self._records.items() if w==ws]

    def get(self, ws, rid):
        if (ws,rid) not in self._records:
            raise KeyError("record not found")
        return self._records[(ws,rid)]

    def act(self, ws, rid, action, actor, op, reason=None):
        if (ws,op) in self._ops:
            raise ValueError("operation replay detected")
        r=self.get(ws,rid)
        if r.state==FailoverRecoveryState.BLOCKED and action not in {"revoke","archive"}:
            raise ValueError("risk brain hard block")

        if action=="submit-review":
            new=FailoverRecoveryState.REVIEW_REQUIRED
        elif action=="approve":
            if r.state!=FailoverRecoveryState.REVIEW_REQUIRED:
                raise ValueError("review required before approval")
            new=FailoverRecoveryState.APPROVED
        elif action=="mark-recovery-ready":
            if r.state!=FailoverRecoveryState.APPROVED:
                raise ValueError("human approval required before recovery readiness")
            if r.scores.failover_trust < .9 or r.scores.primary_recovery_readiness < .9:
                raise ValueError("recovery readiness thresholds not met")
            new=FailoverRecoveryState.RECOVERY_READY
        elif action=="hold":
            new=FailoverRecoveryState.HOLD
        elif action=="revoke":
            new=FailoverRecoveryState.REVOKED
        elif action=="archive":
            new=FailoverRecoveryState.ARCHIVED
        else:
            raise ValueError("unsupported action")

        r=r.model_copy(update={
            "state":new,
            "approved_by":actor if action=="approve" else r.approved_by,
            "version":r.version+1,
        })
        self._records[(ws,rid)]=r
        self._ops.add((ws,op))
        self._audit.append({"workspace_id":ws,"record_id":rid,"action":action,"actor":actor,"operation_id":op,"reason":reason})
        return r

    def audit(self, ws):
        return [x for x in self._audit if x["workspace_id"]==ws]


failover_outcome_recovery_service=FailoverOutcomeRecoveryService()
