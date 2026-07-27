from hashlib import sha256
from json import dumps
from typing import Dict, Set, Tuple
from uuid import uuid4
from app.schemas.dispatch_health_failover import *

PROTECTED={"fund-movement","order-submit","trade-execute","credential-mutate","permission-escalate","disable-safety-control"}

class DispatchHealthFailoverService:
    def __init__(self):
        self._records:Dict[Tuple[str,str],DispatchHealthRecord]={}; self._sources:Set[Tuple[str,str]]=set(); self._ops:Set[Tuple[str,str]]=set(); self._audit=[]
    def status(self):
        return {"module":"dispatch-health-evaluation-governed-failover-trigger-verification","version":"21.135","external_execution_enabled":False,"autonomous_failover_enabled":False,"human_approval_required":True,"risk_brain_authoritative":True}
    @staticmethod
    def _digest(v): return sha256(dumps(v,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
    def create(self,p:DispatchHealthCreate):
        key=(p.workspace_id,p.source_key)
        if key in self._sources: raise ValueError("duplicate source_key for workspace")
        if p.operation in PROTECTED or p.upstream_risk_brain_blocked:
            state=DispatchHealthState.BLOCKED
        else:
            state=DispatchHealthState.EVIDENCE_READY
        e=p.evidence; triggers=[]
        if not e.primary_available: triggers.append("primary-unavailable")
        if e.latency_ms>p.max_latency_ms: triggers.append("latency-degraded")
        if e.receipt_reconciliation<p.min_receipt_reconciliation: triggers.append("receipt-reconciliation-degraded")
        if not e.worker_heartbeat_ok: triggers.append("worker-heartbeat-lost")
        if not e.gateway_healthy: triggers.append("gateway-unhealthy")
        if not e.adapter_healthy: triggers.append("adapter-unhealthy")
        health=sum([e.primary_available,e.latency_ms<=p.max_latency_ms,e.receipt_reconciliation>=p.min_receipt_reconciliation,e.worker_heartbeat_ok,e.gateway_healthy,e.adapter_healthy])/6
        health*=e.confidence*e.freshness
        fail_conf=(1-health) if triggers else 0
        residual=min(1,1-health)
        scores=DispatchHealthScores(health_assurance=round(health,4),failover_confidence=round(fail_conf,4),residual_risk=round(residual,4))
        evidence_digest=self._digest(e.model_dump())
        decision_digest=self._digest({"plan":p.dispatch_plan_digest,"operation":p.operation,"target":p.target,"triggers":triggers,"scores":scores.model_dump()})
        r=DispatchHealthRecord(record_id=str(uuid4()),workspace_id=p.workspace_id,source_key=p.source_key,state=state,dispatch_plan_id=p.dispatch_plan_id,dispatch_plan_digest=p.dispatch_plan_digest,operation=p.operation,target=p.target,primary_adapter_id=p.primary_adapter_id,primary_worker_id=p.primary_worker_id,standby_adapter_id=p.standby_adapter_id,standby_worker_id=p.standby_worker_id,triggers=triggers,scores=scores,evidence_digest=evidence_digest,decision_digest=decision_digest)
        self._records[(p.workspace_id,r.record_id)]=r; self._sources.add(key); self._audit.append({"workspace_id":p.workspace_id,"record_id":r.record_id,"action":"create","actor":p.requested_by,"digest":decision_digest}); return r
    def list(self,ws): return [r for (w,_),r in self._records.items() if w==ws]
    def get(self,ws,rid):
        if (ws,rid) not in self._records: raise KeyError("record not found")
        return self._records[(ws,rid)]
    def act(self,ws,rid,action,actor,op,reason=None):
        if (ws,op) in self._ops: raise ValueError("operation replay detected")
        r=self.get(ws,rid)
        if r.state==DispatchHealthState.BLOCKED and action not in {"revoke","archive"}: raise ValueError("risk brain hard block")
        transitions={"evaluate":DispatchHealthState.DEGRADED if r.triggers else DispatchHealthState.HEALTHY,"submit-review":DispatchHealthState.REVIEW_REQUIRED,"approve":DispatchHealthState.APPROVED,"authorize-failover":DispatchHealthState.FAILOVER_AUTHORIZED,"revoke":DispatchHealthState.REVOKED,"archive":DispatchHealthState.ARCHIVED}
        if action not in transitions: raise ValueError("unsupported action")
        if action=="authorize-failover":
            if r.state!=DispatchHealthState.APPROVED: raise ValueError("human approval required before failover authorization")
            if not r.triggers: raise ValueError("no verified failover trigger")
        new=transitions[action]
        r=r.model_copy(update={"state":new,"approved_by":actor if action=="approve" else r.approved_by,"version":r.version+1}); self._records[(ws,rid)]=r; self._ops.add((ws,op)); self._audit.append({"workspace_id":ws,"record_id":rid,"action":action,"actor":actor,"operation_id":op,"reason":reason}); return r
    def audit(self,ws): return [x for x in self._audit if x["workspace_id"]==ws]

dispatch_health_failover_service=DispatchHealthFailoverService()
