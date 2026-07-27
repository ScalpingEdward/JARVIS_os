from __future__ import annotations
import hashlib, json
from typing import Dict, Set, Tuple
from uuid import uuid4
from app.schemas.post_execution_outcome_validation import *

PROTECTED_OPERATIONS={'fund-movement','order-submit','trade-execute','credential-mutate','permission-escalate','safety-controls-disable','repo-delete','repo-force-push'}

class PostExecutionOutcomeValidationService:
    def __init__(self):
        self._records:Dict[Tuple[str,str],OutcomeValidationRecord]={}; self._sources:Set[Tuple[str,str]]=set(); self._ops:Set[Tuple[str,str]]=set(); self._audit=[]
    def status(self):
        return {'module':'post-execution-outcome-validation-side-effect-attestation','version':'21.131','governance_only':True,'external_network_client_enabled':False,'write_execution_enabled':False,'trading_execution_enabled':False,'human_approval_required':True,'risk_brain_authoritative':True}
    @staticmethod
    def _digest(data): return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def create(self,p:OutcomeValidationCreate):
        key=(p.workspace_id,p.source_key)
        if key in self._sources: raise ValueError('duplicate source_key for workspace')
        flags=[]
        if p.upstream_risk_brain_blocked: flags.append('risk-brain-hard-block')
        if p.operation.lower() in PROTECTED_OPERATIONS: flags.append('risk-brain-hard-block')
        if p.receipt_status.lower() not in {'succeeded','success','ok','200'}: flags.append('receipt-status-not-successful')
        failed=[x.key for x in p.postconditions if not x.passed]
        if failed: flags.append('postcondition-mismatch:'+','.join(sorted(failed)))
        se=p.side_effects
        side_effect_free=not any([se.write_detected,se.credential_mutation_detected,se.permission_mutation_detected,se.fund_movement_detected,se.order_submission_detected,se.trading_execution_detected,se.repository_mutation_detected])
        if not side_effect_free: flags.append('prohibited-side-effect-detected')
        passed=sum(1 for x in p.postconditions if x.passed); total=len(p.postconditions)
        validation_score=1.0 if total==0 else round(passed/total,4)
        state=OutcomeValidationState.BLOCKED if 'risk-brain-hard-block' in flags else (OutcomeValidationState.MISMATCH if flags else OutcomeValidationState.EVIDENCE_READY)
        digest=self._digest({'reconciliation_digest':p.reconciliation_digest,'permit_id':p.permit_id,'authorization_chain_digest':p.authorization_chain_digest,'receipt_digest':p.receipt_digest,'response_digest':p.response_digest,'operation':p.operation,'target':p.target,'method':p.method.upper(),'postconditions':[x.model_dump() for x in p.postconditions],'side_effects':se.model_dump(),'flags':sorted(flags)})
        r=OutcomeValidationRecord(record_id=str(uuid4()),workspace_id=p.workspace_id,source_key=p.source_key,state=state,reconciliation_record_id=p.reconciliation_record_id,reconciliation_digest=p.reconciliation_digest,permit_id=p.permit_id,authorization_chain_digest=p.authorization_chain_digest,receipt_digest=p.receipt_digest,response_digest=p.response_digest,operation=p.operation,target=p.target,method=p.method.upper(),receipt_status=p.receipt_status,postconditions=p.postconditions,side_effects=se,validation_score=validation_score,side_effect_free=side_effect_free,risk_flags=sorted(set(flags)),attestation_digest=digest)
        self._records[(p.workspace_id,r.record_id)]=r; self._sources.add(key); self._audit.append({'workspace_id':p.workspace_id,'record_id':r.record_id,'action':'create','actor':p.requested_by,'attestation_digest':digest}); return r
    def list(self,ws): return [r for (w,_),r in self._records.items() if w==ws]
    def get(self,ws,rid):
        if (ws,rid) not in self._records: raise KeyError('record not found')
        return self._records[(ws,rid)]
    def act(self,ws,rid,action,actor,op_id,reason=None):
        if (ws,op_id) in self._ops: raise ValueError('operation replay detected')
        r=self.get(ws,rid); transitions={'submit-review':OutcomeValidationState.REVIEW_REQUIRED,'verify':OutcomeValidationState.VERIFIED,'approve':OutcomeValidationState.APPROVED,'attest':OutcomeValidationState.ATTESTED,'revoke':OutcomeValidationState.REVOKED,'archive':OutcomeValidationState.ARCHIVED}
        if action not in transitions: raise ValueError('unsupported action')
        if action in {'verify','approve','attest'} and r.risk_flags: raise ValueError('unresolved validation findings block progression')
        if action=='attest' and r.state!=OutcomeValidationState.APPROVED: raise ValueError('human approval required before attestation')
        nr=r.model_copy(update={'state':transitions[action],'approved_by':actor if action=='approve' else r.approved_by,'version':r.version+1}); self._records[(ws,rid)]=nr; self._ops.add((ws,op_id)); self._audit.append({'workspace_id':ws,'record_id':rid,'action':action,'actor':actor,'operation_id':op_id,'reason':reason,'attestation_digest':nr.attestation_digest}); return nr
    def audit(self,ws): return [x for x in self._audit if x['workspace_id']==ws]

post_execution_outcome_validation_service=PostExecutionOutcomeValidationService()
