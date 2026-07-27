from hashlib import sha256
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4
from app.schemas.decision_execution_proposal import *

class DecisionExecutionProposalService:
    PROTECTED={"fund-movement","order-submit","trade-execute","credential-mutate","permission-escalate","safety-control-disable"}
    def __init__(self): self._records:Dict[Tuple[str,str],ProposalRecord]={}; self._sources:Set[Tuple[str,str]]=set(); self._ops:Set[Tuple[str,str]]=set(); self._audit:List[dict]=[]
    def status(self): return {"module":"decision-to-execution-proposal-governance","version":"21.126","proposal_generation_enabled":True,"proposal_execution_enabled":False,"external_writes_enabled":False,"fund_movement_enabled":False,"trading_execution_enabled":False,"human_authorization_required":True,"risk_brain_authoritative":True}
    def create(self,p:ProposalCreate):
        if p.decision_state not in {"approved","ready"}: raise ValueError("decision must be approved/ready")
        key=(p.workspace_id,p.source_key)
        if key in self._sources: raise ValueError("duplicate source_key for workspace")
        flags=[]
        ops={a.operation for a in p.actions}
        protected=sorted(ops & self.PROTECTED)
        if protected: flags += [f"protected-operation:{x}" for x in protected] + ["risk-brain-hard-block"]
        if p.criticality>=.9 and (p.decision_confidence<.6 or p.residual_risk>.5): flags.append("risk-brain-hard-block")
        rev=mean(a.reversibility for a in p.actions); obs=mean(a.observability for a in p.actions); val=mean(a.validation_readiness for a in p.actions); bra=mean(1-a.blast_radius for a in p.actions)
        scores=ProposalScores(reversibility=round(rev,4),observability=round(obs,4),validation_readiness=round(val,4),blast_radius_assurance=round(bra,4),aggregate_assurance=round(mean([rev,obs,val,bra])*p.decision_confidence,4))
        raw=f"{p.workspace_id}|{p.decision_record_id}|{p.decision_packet_digest}|"+"|".join(f"{a.action_id}:{a.target}:{a.operation}" for a in p.actions)
        digest=sha256(raw.encode()).hexdigest()
        state=ProposalState.BLOCKED if "risk-brain-hard-block" in flags else ProposalState.REVIEW_REQUIRED
        r=ProposalRecord(record_id=str(uuid4()),workspace_id=p.workspace_id,source_key=p.source_key,decision_record_id=p.decision_record_id,state=state,proposal_digest=digest,scores=scores,risk_flags=sorted(set(flags)))
        self._records[(p.workspace_id,r.record_id)]=r; self._sources.add(key); self._audit_event(r,"create",p.requested_by,f"create:{r.record_id}"); return r
    def list(self,ws): return [r for (w,_),r in self._records.items() if w==ws]
    def get(self,ws,rid):
        if (ws,rid) not in self._records: raise KeyError("record not found")
        return self._records[(ws,rid)]
    def act(self,rid,p:ProposalAction):
        op=(p.workspace_id,p.operation_id)
        if op in self._ops: raise ValueError("operation replay detected")
        r=self.get(p.workspace_id,rid)
        trans={"approve":ProposalState.APPROVED,"authorize":ProposalState.AUTHORIZED,"prepare":ProposalState.READY,"reject":ProposalState.REJECTED,"revoke":ProposalState.REVOKED,"archive":ProposalState.ARCHIVED}
        if p.action not in trans: raise ValueError("unsupported action")
        if p.action=="approve" and r.risk_flags: raise ValueError("unresolved proposal findings block approval")
        if p.action=="authorize" and r.state!=ProposalState.APPROVED: raise ValueError("approval required before authorization")
        if p.action=="prepare" and r.state!=ProposalState.AUTHORIZED: raise ValueError("authorization required before ready")
        u=r.model_copy(update={"state":trans[p.action],"approved_by":p.actor if p.action=="approve" else r.approved_by,"authorized_by":p.actor if p.action=="authorize" else r.authorized_by,"version":r.version+1})
        self._records[(p.workspace_id,rid)]=u; self._ops.add(op); self._audit_event(u,p.action,p.actor,p.operation_id); return u
    def audit(self,ws): return [x for x in self._audit if x["workspace_id"]==ws]
    def _audit_event(self,r,action,actor,operation_id):
        raw=f"{r.workspace_id}|{r.record_id}|{action}|{actor}|{operation_id}|{r.version}"
        self._audit.append({"workspace_id":r.workspace_id,"record_id":r.record_id,"action":action,"actor":actor,"operation_id":operation_id,"event_digest":sha256(raw.encode()).hexdigest()})

decision_execution_proposal_service=DecisionExecutionProposalService()
