from hashlib import sha256
from typing import Dict, List, Set, Tuple
from uuid import uuid4
from app.schemas.proposal_safe_execution_contract_binding import BindingState, ExecutionBindingAction, ExecutionBindingCreate, ExecutionBindingRecord

class ProposalSafeExecutionContractBindingService:
    PROTECTED_OPERATIONS={"fund-movement","order-submit","trade-execute","credential-mutate","permission-escalate","safety-control-disable"}
    def __init__(self):
        self._records: Dict[Tuple[str,str],ExecutionBindingRecord]={}; self._sources:Set[Tuple[str,str]]=set(); self._ops:Set[Tuple[str,str]]=set(); self._audit:List[dict]=[]
    def status(self):
        return {"module":"proposal-safe-execution-contract-binding","version":"21.127","binding_enabled":True,"execution_enabled":False,"sandbox_bypass_enabled":False,"adapter_bypass_enabled":False,"gateway_bypass_enabled":False,"worker_bypass_enabled":False,"human_authorization_required":True,"risk_brain_authoritative":True}
    def create(self,p:ExecutionBindingCreate):
        source=(p.workspace_id,p.source_key)
        if source in self._sources: raise ValueError("duplicate source_key for workspace")
        flags=[]
        if p.proposal_state not in {"approved","authorized","ready"} or not p.proposal_authorized: flags.append("proposal-not-authorized")
        if p.operation in self.PROTECTED_OPERATIONS: flags += [f"protected-operation:{p.operation}","risk-brain-hard-block"]
        if p.execution_enabled: flags += ["direct-execution-requested","risk-brain-hard-block"]
        if not all([p.sandbox_policy_id,p.adapter_policy_id,p.gateway_policy_id,p.worker_policy_id]): flags += ["control-chain-incomplete","risk-brain-hard-block"]
        digest=sha256(f"{p.workspace_id}|{p.proposal_record_id}|{p.proposal_digest}|{p.safe_execution_contract_id}|{p.safe_execution_contract_digest}|{p.sandbox_policy_id}|{p.adapter_policy_id}|{p.gateway_policy_id}|{p.worker_policy_id}|{p.operation}|{p.target}".encode()).hexdigest()
        state=BindingState.BLOCKED if "risk-brain-hard-block" in flags else BindingState.REVIEW_REQUIRED
        r=ExecutionBindingRecord(record_id=str(uuid4()),workspace_id=p.workspace_id,source_key=p.source_key,state=state,binding_digest=digest,proposal_record_id=p.proposal_record_id,safe_execution_contract_id=p.safe_execution_contract_id,operation=p.operation,target=p.target,risk_flags=sorted(set(flags)),execution_enabled=False)
        self._records[(p.workspace_id,r.record_id)]=r; self._sources.add(source); self._audit_event(r,"create",p.requested_by,f"create:{r.record_id}"); return r
    def list(self,ws): return [r for (w,_),r in self._records.items() if w==ws]
    def get(self,ws,rid):
        if (ws,rid) not in self._records: raise KeyError("record not found")
        return self._records[(ws,rid)]
    def act(self,rid,p:ExecutionBindingAction):
        receipt=(p.workspace_id,p.operation_id)
        if receipt in self._ops: raise ValueError("operation replay detected")
        r=self.get(p.workspace_id,rid)
        transitions={"approve":BindingState.APPROVED,"bind":BindingState.BOUND,"mark-ready":BindingState.READY,"revoke":BindingState.REVOKED,"archive":BindingState.ARCHIVED}
        if p.action not in transitions: raise ValueError("unsupported action")
        if p.action=="approve" and r.risk_flags: raise ValueError("unresolved binding findings block approval")
        if p.action=="bind" and r.state!=BindingState.APPROVED: raise ValueError("approval required before binding")
        if p.action=="mark-ready" and r.state!=BindingState.BOUND: raise ValueError("binding required before ready")
        r=r.model_copy(update={"state":transitions[p.action],"approved_by":p.actor if p.action=="approve" else r.approved_by,"bound_by":p.actor if p.action=="bind" else r.bound_by,"version":r.version+1})
        self._records[(p.workspace_id,rid)]=r; self._ops.add(receipt); self._audit_event(r,p.action,p.actor,p.operation_id,p.reason); return r
    def audit(self,ws): return [e for e in self._audit if e["workspace_id"]==ws]
    def _audit_event(self,r,action,actor,op,detail=None):
        raw=f"{r.workspace_id}|{r.record_id}|{action}|{actor}|{op}|{r.version}|{r.binding_digest}"
        self._audit.append({"workspace_id":r.workspace_id,"record_id":r.record_id,"action":action,"actor":actor,"operation_id":op,"detail":detail,"event_digest":sha256(raw.encode()).hexdigest()})

proposal_safe_execution_contract_binding_service=ProposalSafeExecutionContractBindingService()
