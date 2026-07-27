from __future__ import annotations
import hashlib, json
from typing import Dict, Set, Tuple
from uuid import uuid4
from app.schemas.trust_calibrated_execution_selection import *

PROTECTED={'fund-movement','order-submit','trade-execute','credential-mutation','permission-escalation','disable-safety-controls'}

class TrustCalibratedExecutionSelectionService:
    def __init__(self):
        self._records:Dict[Tuple[str,str],SelectionRecord]={}; self._sources:Set[Tuple[str,str]]=set(); self._ops:Set[Tuple[str,str]]=set(); self._audit=[]
    def status(self):
        return {'module':'trust-calibrated-adapter-worker-selection-governance','version':'21.133','selection_only':True,'autonomous_routing_mutation_enabled':False,'permission_expansion_enabled':False,'external_execution_enabled':False,'trading_execution_enabled':False,'human_approval_required':True,'risk_brain_authoritative':True}
    def create(self,p:SelectionCreate):
        if (p.workspace_id,p.source_key) in self._sources: raise ValueError('duplicate source_key for workspace')
        flags=[]
        if p.operation.lower() in PROTECTED: flags.append('risk-brain-hard-block')
        ranked=[]
        for c in p.candidates:
            reasons=[]
            if not c.active: reasons.append('candidate-inactive')
            if c.risk_brain_blocked: reasons.append('candidate-risk-brain-blocked')
            if c.trust_score<p.min_trust: reasons.append('trust-below-floor')
            if c.confidence<p.min_confidence: reasons.append('confidence-below-floor')
            if min(c.capability_match,c.permission_match,c.sandbox_match,c.policy_match)<1.0: reasons.append('mandatory-control-mismatch')
            score=round((c.trust_score*.30+c.reliability*.20+c.latency_quality*.10+c.freshness*.10+c.confidence*.10+c.capability_match*.05+c.permission_match*.05+c.sandbox_match*.05+c.policy_match*.05),4)
            eligible=not reasons
            ranked.append(RankedCandidate(adapter_id=c.adapter_id,worker_id=c.worker_id,selection_score=score,eligible=eligible,reasons=reasons))
        ranked.sort(key=lambda x:x.selection_score,reverse=True)
        eligible=[x for x in ranked if x.eligible]
        if not eligible: flags.append('no-eligible-candidate')
        if any('candidate-risk-brain-blocked' in x.reasons for x in ranked): flags.append('candidate-risk-brain-blocked')
        selected=eligible[0] if eligible else None
        digest=hashlib.sha256(json.dumps({'workspace_id':p.workspace_id,'source_key':p.source_key,'operation':p.operation,'target':p.target,'ranked':[x.model_dump() for x in ranked]},sort_keys=True).encode()).hexdigest()
        state=SelectionState.BLOCKED if 'risk-brain-hard-block' in flags else SelectionState.EVIDENCE_READY
        r=SelectionRecord(record_id=str(uuid4()),workspace_id=p.workspace_id,source_key=p.source_key,operation=p.operation,target=p.target,state=state,ranked_candidates=ranked,selected_adapter_id=selected.adapter_id if selected else None,selected_worker_id=selected.worker_id if selected else None,selection_digest=digest,risk_flags=sorted(set(flags)))
        self._records[(p.workspace_id,r.record_id)]=r; self._sources.add((p.workspace_id,p.source_key)); self._audit.append({'workspace_id':p.workspace_id,'record_id':r.record_id,'action':'create','actor':p.requested_by,'digest':digest}); return r
    def list(self,ws): return [r for (w,_),r in self._records.items() if w==ws]
    def get(self,ws,rid):
        if (ws,rid) not in self._records: raise KeyError('record not found')
        return self._records[(ws,rid)]
    def act(self,ws,rid,action,actor,op,reason=None):
        if (ws,op) in self._ops: raise ValueError('operation replay detected')
        r=self.get(ws,rid)
        transitions={'submit-review':SelectionState.REVIEW_REQUIRED,'approve':SelectionState.APPROVED,'mark-ready':SelectionState.READY,'revoke':SelectionState.REVOKED,'archive':SelectionState.ARCHIVED}
        if action not in transitions: raise ValueError('unsupported action')
        if action=='approve' and r.risk_flags: raise ValueError('unresolved selection findings block approval')
        if action=='mark-ready' and r.state!=SelectionState.APPROVED: raise ValueError('human approval required before ready state')
        r=r.model_copy(update={'state':transitions[action],'approved_by':actor if action=='approve' else r.approved_by,'version':r.version+1}); self._records[(ws,rid)]=r; self._ops.add((ws,op)); self._audit.append({'workspace_id':ws,'record_id':rid,'action':action,'actor':actor,'operation_id':op,'reason':reason}); return r
    def audit(self,ws): return [x for x in self._audit if x['workspace_id']==ws]

trust_calibrated_execution_selection_service=TrustCalibratedExecutionSelectionService()
