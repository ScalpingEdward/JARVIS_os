from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4
from app.schemas.agent_operational_performance_trend import *

class AgentOperationalPerformanceTrendService:
    def __init__(self): self._records:Dict[Tuple[str,str],OperationalTrendRecord]={}; self._sources:Set[Tuple[str,str]]=set(); self._ops:Set[Tuple[str,str]]=set(); self._audit=[]
    @staticmethod
    def _c(v): return round(max(0.,min(1.,v)),4)
    def status(self): return {"module":"agent-operational-performance-trend-governance","version":"21.109","governance_only":True,"automatic_tuning_enabled":False,"autoscaling_enabled":False,"automatic_remediation_enabled":False,"traffic_shift_enabled":False,"runtime_restart_enabled":False,"agent_execution_enabled":False,"trading_execution_enabled":False,"human_approval_required":True,"risk_brain_authoritative":True}
    def create(self,p:OperationalTrendCreate):
        key=(p.workspace_id,p.source_key)
        if key in self._sources: raise ValueError("duplicate source_key for workspace")
        scores,disp,flags=self._assess(p); state=OperationalTrendState.BLOCKED if "risk-brain-hard-block" in flags else OperationalTrendState.EVIDENCE_READY
        r=OperationalTrendRecord(record_id=str(uuid4()),workspace_id=p.workspace_id,source_key=p.source_key,state=state,scores=scores,dispositions=disp,risk_flags=flags)
        self._records[(p.workspace_id,r.record_id)]=r; self._sources.add(key); self._audit.append({"workspace_id":p.workspace_id,"record_id":r.record_id,"action":"create","actor":p.requested_by}); return r
    def list(self,ws): return [r for (w,_),r in self._records.items() if w==ws]
    def get(self,ws,rid):
        if (ws,rid) not in self._records: raise KeyError("record not found")
        return self._records[(ws,rid)]
    def act(self,ws,rid,action,actor,op,reason=None):
        if (ws,op) in self._ops: raise ValueError("operation replay detected")
        r=self.get(ws,rid); transitions={"assess":OperationalTrendState.ASSESSED,"submit-review":OperationalTrendState.REVIEW_REQUIRED,"approve":OperationalTrendState.APPROVED,"activate":OperationalTrendState.ACTIVE,"monitor":OperationalTrendState.MONITORING,"mark-healthy":OperationalTrendState.HEALTHY,"suspend":OperationalTrendState.SUSPENDED,"revoke":OperationalTrendState.REVOKED,"archive":OperationalTrendState.ARCHIVED}
        if action not in transitions: raise ValueError("unsupported action")
        if action=="approve" and r.risk_flags: raise ValueError("unresolved operational-performance findings block approval")
        if action in {"activate","monitor","mark-healthy"} and r.state not in {OperationalTrendState.APPROVED,OperationalTrendState.ACTIVE,OperationalTrendState.MONITORING,OperationalTrendState.HEALTHY}: raise ValueError("human approval required before governed active state")
        r=r.model_copy(update={"state":transitions[action],"approved_by":actor if action=="approve" else r.approved_by,"version":r.version+1}); self._records[(ws,rid)]=r; self._ops.add((ws,op)); self._audit.append({"workspace_id":ws,"record_id":rid,"action":action,"actor":actor,"operation_id":op,"reason":reason}); return r
    def audit(self,ws): return [x for x in self._audit if x["workspace_id"]==ws]
    def _assess(self,p):
        obs=p.observations; perf=mean(mean([o.availability_trend,o.latency_trend,o.error_rate_trend,o.throughput_trend,o.business_kpi_trend]) for o in obs); eff=mean(mean([o.cost_efficiency,o.resource_efficiency,o.alert_quality]) for o in obs); dep=mean(o.dependency_health for o in obs); slo=mean(mean([o.slo_posture,o.error_budget_posture]) for o in obs); conf=mean(o.confidence*o.freshness for o in obs); agg=self._c(mean([perf,eff,dep,slo])*conf)
        dispositions=[]; flags=[]; risks=[]
        for o in obs:
            actions=[]; signal="healthy"; op_perf=mean([o.availability_trend,o.latency_trend,o.error_rate_trend,o.throughput_trend,o.business_kpi_trend]); op_eff=mean([o.cost_efficiency,o.resource_efficiency,o.alert_quality]); risk=self._c((1-op_perf)*.38+(1-op_eff)*.18+(1-o.dependency_health)*.14+(1-o.slo_posture)*.10+(1-o.error_budget_posture)*.08+min(o.operator_interventions/5,1)*.04+min(o.sustained_degradation_events/3,1)*.05+min(o.dependency_incidents/3,1)*.03); risks.append(risk)
            if op_perf<p.min_performance or o.sustained_degradation_events: signal="performance-alert"; actions.append("performance-trend-review"); flags.append(f"performance-alert:{o.agent_id}:{o.window_id}")
            if op_eff<p.min_efficiency: signal="efficiency-alert"; actions.append("efficiency-trend-review"); flags.append(f"efficiency-alert:{o.agent_id}:{o.window_id}")
            if o.dependency_health<p.min_performance or o.dependency_incidents: signal="dependency-alert"; actions.append("dependency-trend-review"); flags.append(f"dependency-alert:{o.agent_id}:{o.window_id}")
            if o.operator_interventions>=3: signal="intervention-alert"; actions.append("operator-intervention-review"); flags.append(f"intervention-alert:{o.agent_id}:{o.window_id}")
            if min(o.slo_posture,o.error_budget_posture)<p.min_performance: signal="slo-alert"; actions.append("slo-error-budget-review"); flags.append(f"slo-alert:{o.agent_id}:{o.window_id}")
            if risk>p.max_residual_risk: actions.append("operational-performance-risk-committee"); flags.append(f"residual-risk-breach:{o.agent_id}:{o.window_id}")
            if o.criticality>=.9 and (o.sustained_degradation_events>1 or risk>=.6): actions.append("risk-brain-hard-block"); flags.append("risk-brain-hard-block")
            dispositions.append(OperationalTrendDisposition(agent_id=o.agent_id,agent_version=o.agent_version,window_id=o.window_id,assurance=self._c(1-risk),residual_risk=risk,lifecycle_signal=signal,required_actions=sorted(set(actions))))
        scores=OperationalTrendScores(performance_assurance=self._c(perf),efficiency_assurance=self._c(eff),dependency_assurance=self._c(dep),slo_assurance=self._c(slo),aggregate_assurance=agg,aggregate_residual_risk=self._c(mean(risks)),confidence=self._c(conf)); return scores,dispositions,sorted(set(flags))

agent_operational_performance_trend_service=AgentOperationalPerformanceTrendService()
