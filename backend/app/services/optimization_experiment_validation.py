from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4
from app.schemas.optimization_experiment_validation import *

class OptimizationExperimentValidationService:
    def __init__(self): self._records:Dict[Tuple[str,str],ExperimentRecord]={}; self._sources:Set[Tuple[str,str]]=set(); self._ops:Set[Tuple[str,str]]=set(); self._audit=[]
    @staticmethod
    def _c(v): return round(max(0.,min(1.,v)),4)
    def status(self): return {"module":"optimization-experiment-validation-governance","version":"21.111","governance_only":True,"experiment_execution_enabled":False,"configuration_mutation_enabled":False,"deployment_enabled":False,"traffic_shift_enabled":False,"automatic_rollback_enabled":False,"agent_execution_enabled":False,"trading_execution_enabled":False,"human_approval_required":True,"risk_brain_authoritative":True}
    def create(self,p:ExperimentCreate):
        key=(p.workspace_id,p.source_key)
        if key in self._sources: raise ValueError("duplicate source_key for workspace")
        disp,flags=self._assess(p); state=ExperimentState.BLOCKED if "risk-brain-hard-block" in flags else ExperimentState.EVIDENCE_READY
        r=ExperimentRecord(record_id=str(uuid4()),workspace_id=p.workspace_id,source_key=p.source_key,state=state,dispositions=disp,risk_flags=flags)
        self._records[(p.workspace_id,r.record_id)]=r; self._sources.add(key); self._audit.append({"workspace_id":p.workspace_id,"record_id":r.record_id,"action":"create","actor":p.requested_by}); return r
    def list(self,ws): return [r for (w,_),r in self._records.items() if w==ws]
    def get(self,ws,rid):
        if (ws,rid) not in self._records: raise KeyError("record not found")
        return self._records[(ws,rid)]
    def act(self,ws,rid,action,actor,op,reason=None):
        if (ws,op) in self._ops: raise ValueError("operation replay detected")
        r=self.get(ws,rid); transitions={"assess":ExperimentState.ASSESSED,"submit-review":ExperimentState.REVIEW_REQUIRED,"approve":ExperimentState.APPROVED,"validate":ExperimentState.VALIDATED,"reject":ExperimentState.REJECTED,"archive":ExperimentState.ARCHIVED}
        if action not in transitions: raise ValueError("unsupported action")
        if action=="approve" and r.risk_flags: raise ValueError("unresolved experiment findings block approval")
        if action=="validate" and r.state!=ExperimentState.APPROVED: raise ValueError("human approval required before validation")
        r=r.model_copy(update={"state":transitions[action],"approved_by":actor if action=="approve" else r.approved_by,"version":r.version+1}); self._records[(ws,rid)]=r; self._ops.add((ws,op)); self._audit.append({"workspace_id":ws,"record_id":rid,"action":action,"actor":actor,"operation_id":op,"reason":reason}); return r
    def audit(self,ws): return [x for x in self._audit if x["workspace_id"]==ws]
    def _assess(self,p):
        out:List[ExperimentDisposition]=[]; flags=[]
        for o in p.observations:
            gain=o.candidate_score-o.baseline_score; actions=[]; signal="candidate-ready"
            assurance=self._c(mean([o.reliability_score,o.latency_score,o.cost_score,o.resource_score,o.shadow_coverage,o.ab_evidence,o.statistical_confidence,o.rollback_readiness]))
            residual=self._c((1-o.reliability_score)*.18+(1-o.latency_score)*.08+(1-o.cost_score)*.06+(1-o.resource_score)*.06+(1-o.shadow_coverage)*.12+(1-o.ab_evidence)*.14+(1-o.statistical_confidence)*.18+(1-o.rollback_readiness)*.12+min(o.regression_count/3,1)*.06)
            if gain<p.min_gain: signal="gain-alert"; actions.append("candidate-value-review"); flags.append(f"gain-alert:{o.candidate_id}")
            if o.statistical_confidence<p.min_confidence or o.ab_evidence<p.min_confidence: signal="evidence-alert"; actions.append("experiment-evidence-review"); flags.append(f"evidence-alert:{o.candidate_id}")
            if o.regression_count>0: signal="regression-alert"; actions.append("regression-review"); flags.append(f"regression-alert:{o.candidate_id}")
            if o.rollback_readiness<p.min_rollback: signal="rollback-alert"; actions.append("rollback-readiness-review"); flags.append(f"rollback-alert:{o.candidate_id}")
            if residual>p.max_residual_risk: actions.append("experiment-risk-committee"); flags.append(f"residual-risk-breach:{o.candidate_id}")
            if o.criticality>=.9 and (o.regression_count>1 or residual>=.6): actions.append("risk-brain-hard-block"); flags.append("risk-brain-hard-block"); signal="blocked"
            out.append(ExperimentDisposition(candidate_id=o.candidate_id,expected_gain=round(gain,4),assurance=assurance,residual_risk=residual,signal=signal,required_actions=sorted(set(actions))))
        return out,sorted(set(flags))

optimization_experiment_validation_service=OptimizationExperimentValidationService()
