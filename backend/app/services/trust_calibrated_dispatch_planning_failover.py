from __future__ import annotations
import hashlib, json
from typing import Dict, Set, Tuple
from uuid import uuid4
from app.schemas.trust_calibrated_dispatch_planning_failover import *

PROTECTED={"fund-movement","order-submit","trade-execute","credential-mutate","permission-escalate","disable-safety-controls"}

class TrustCalibratedDispatchPlanningFailoverService:
    def __init__(self): self._records:Dict[Tuple[str,str],DispatchPlanRecord]={}; self._sources:Set[Tuple[str,str]]=set(); self._ops:Set[Tuple[str,str]]=set(); self._audit=[]
    @staticmethod
    def status(): return {"module":"trust-calibrated-dispatch-planning-failover-governance","version":"21.134","dispatch_execution_enabled":False,"autonomous_failover_enabled":False,"human_approval_required":True,"risk_brain_authoritative":True}
    @staticmethod
    def _score(c:DispatchCandidate): return round(.35*c.trust_score+.25*c.reliability+.15*c.latency_quality+.15*c.confidence+.10*c.freshness,4)
    @staticmethod
    def _digest(obj): return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
    def create(self,p:DispatchPlanCreate):
        key=(p.workspace_id,p.source_key)
        if key in self._sources: raise ValueError("duplicate source_key for workspace")
        flags=[]
        if p.operation in PROTECTED: flags.append("risk-brain-hard-block:protected-operation")
        ranked=[]
        for c in p.candidates:
            reasons=[]; eligible=True
            if not c.active: eligible=False; reasons.append("inactive")
            if c.risk_brain_blocked: eligible=False; reasons.append("risk-brain-blocked")
            for ok,name in [(c.capability_match,"capability-mismatch"),(c.permission_match,"permission-mismatch"),(c.sandbox_match,"sandbox-mismatch"),(c.policy_match,"policy-mismatch")]:
                if not ok: eligible=False; reasons.append(name)
            score=self._score(c) if eligible else 0.0
            ranked.append(RankedDispatchCandidate(adapter_id=c.adapter_id,worker_id=c.worker_id,score=score,rank=1,eligible=eligible,reasons=reasons))
        ranked.sort(key=lambda x:(x.eligible,x.score),reverse=True)
        ranked=[x.model_copy(update={"rank":i+1}) for i,x in enumerate(ranked)]
        eligible=[x for x in ranked if x.eligible]
        if len(eligible)<2: flags.append("insufficient-failover-coverage")
        primary=eligible[0] if eligible else None; standby=eligible[1] if len(eligible)>1 else None
        if primary and standby and primary.adapter_id==standby.adapter_id and primary.worker_id==standby.worker_id: flags.append("standby-not-independent")
        state=DispatchPlanState.BLOCKED if any(x.startswith("risk-brain-hard-block") for x in flags) else DispatchPlanState.REVIEW_REQUIRED
        body={"workspace_id":p.workspace_id,"operation":p.operation,"target":p.target,"authorization_chain_id":p.authorization_chain_id,"authorization_chain_digest":p.authorization_chain_digest,"primary":primary.model_dump() if primary else None,"standby":standby.model_dump() if standby else None,"policy":p.failover_policy.model_dump()}
        r=DispatchPlanRecord(record_id=str(uuid4()),workspace_id=p.workspace_id,source_key=p.source_key,operation=p.operation,target=p.target,authorization_chain_id=p.authorization_chain_id,authorization_chain_digest=p.authorization_chain_digest,state=state,primary=primary,standby=standby,ranked_candidates=ranked,failover_policy=p.failover_policy,plan_digest=self._digest(body),risk_flags=sorted(set(flags)))
        self._records[(p.workspace_id,r.record_id)]=r; self._sources.add(key); self._audit.append({"workspace_id":p.workspace_id,"record_id":r.record_id,"action":"create","actor":p.requested_by,"digest":r.plan_digest}); return r
    def list(self,ws): return [r for (w,_),r in self._records.items() if w==ws]
    def get(self,ws,rid):
        if (ws,rid) not in self._records: raise KeyError("record not found")
        return self._records[(ws,rid)]
    def act(self,ws,rid,action,actor,op,reason=None):
        if (ws,op) in self._ops: raise ValueError("operation replay detected")
        r=self.get(ws,rid)
        if action=="approve":
            if r.risk_flags: raise ValueError("unresolved dispatch-plan findings block approval")
            r=r.model_copy(update={"state":DispatchPlanState.APPROVED,"approved_by":actor,"version":r.version+1})
        elif action=="mark-ready":
            if r.state!=DispatchPlanState.APPROVED: raise ValueError("human approval required before ready state")
            r=r.model_copy(update={"state":DispatchPlanState.READY,"version":r.version+1})
        elif action=="mark-degraded": r=r.model_copy(update={"state":DispatchPlanState.DEGRADED,"version":r.version+1})
        elif action=="require-failover":
            if not r.standby or not r.failover_policy.allow_standby_failover: raise ValueError("standby failover unavailable")
            r=r.model_copy(update={"state":DispatchPlanState.FAILOVER_REQUIRED,"version":r.version+1})
        elif action=="suspend": r=r.model_copy(update={"state":DispatchPlanState.SUSPENDED,"version":r.version+1})
        elif action=="revoke": r=r.model_copy(update={"state":DispatchPlanState.REVOKED,"version":r.version+1})
        elif action=="archive": r=r.model_copy(update={"state":DispatchPlanState.ARCHIVED,"version":r.version+1})
        else: raise ValueError("unsupported action")
        self._records[(ws,rid)]=r; self._ops.add((ws,op)); self._audit.append({"workspace_id":ws,"record_id":rid,"action":action,"actor":actor,"operation_id":op,"reason":reason}); return r
    def audit(self,ws): return [x for x in self._audit if x["workspace_id"]==ws]

trust_calibrated_dispatch_planning_failover_service=TrustCalibratedDispatchPlanningFailoverService()
