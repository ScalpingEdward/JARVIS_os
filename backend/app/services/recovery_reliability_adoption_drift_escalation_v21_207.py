import hashlib, json
from app.schemas.recovery_reliability_adoption_drift_escalation_v21_207 import DriftEscalationRequest, DriftEscalationDecision

_SEV={'low':0.15,'medium':0.35,'high':0.65,'critical':1.0}
_seen:set[str]=set()

def _digest(p:dict)->str:
    return hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def evaluate(req:DriftEscalationRequest,human_approved:bool=False)->DriftEscalationDecision:
    reasons=[]
    affected=sorted({c.consumer_id for c in req.affected_consumers})
    healthy=sorted(set(req.healthy_consumers))
    if req.risk_brain_hard_block: reasons.append('risk-brain-hard-block')
    if req.source_state!='drift-detected' or not req.source_human_approved: reasons.append('invalid-source-admission')
    if req.source_id in _seen: reasons.append('duplicate-source')
    if not affected: reasons.append('no-affected-consumers')
    if set(affected)&set(healthy): reasons.append('consumer-set-overlap')
    total=len(set(affected+healthy))
    blast=round(len(affected)/total,4) if total else 1.0
    risks=[_SEV[c.severity]*(0.5+0.5*c.confidence) for c in req.affected_consumers]
    residual=round(sum(risks)/max(len(risks),1),4)
    if blast>req.max_blast_radius: reasons.append('blast-radius-limit-exceeded')
    if residual>req.max_residual_risk: reasons.append('residual-risk-limit-exceeded')
    score=round(max(0.0,1-(0.55*residual+0.45*blast)),4)
    hard={'risk-brain-hard-block','invalid-source-admission','duplicate-source','no-affected-consumers','consumer-set-overlap'}
    if any(r in hard for r in reasons): state='blocked'
    elif reasons: state='review-required'
    elif human_approved:
        state='reconciliation-ready'; _seen.add(req.source_id)
    else: state='review-required'
    payload={'source_id':req.source_id,'workspace_id':req.workspace_id,'baseline_id':req.baseline_id,'baseline_version':req.baseline_version,'baseline_digest':req.baseline_digest,'affected':affected,'healthy':healthy,'blast_radius':blast,'residual_risk':residual,'readiness_score':score,'state':state,'reasons':reasons}
    return DriftEscalationDecision(state=state,readiness_score=score,blast_radius=blast,residual_risk=residual,affected_consumers=affected,healthy_consumers=healthy,reasons=reasons,audit_digest=_digest(payload))

def reset_seen_sources_for_tests()->None:
    _seen.clear()
