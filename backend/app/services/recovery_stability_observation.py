"""PHOENIX v21.142 — recovery stability observation and primary route confidence governance."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from statistics import mean
from typing import Any

PROTECTED_OPERATIONS={"trade-execute","order-submit","fund-move","credential-mutate","permission-expand"}


def _digest(v:Any)->str:
    return sha256(json.dumps(v,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

@dataclass(frozen=True)
class StabilitySample:
    primary_available: bool
    latency_ms: float
    receipt_reconciliation: float
    worker_heartbeat_ok: bool
    gateway_healthy: bool
    adapter_healthy: bool
    confidence: float=1.0
    freshness: float=1.0

@dataclass
class StabilityRecord:
    record_id:str; workspace_id:str; source_key:str; recovery_attestation_id:str; recovery_attestation_digest:str
    operation:str; target:str; state:str; sample_count:int; availability_score:float; latency_score:float
    reconciliation_score:float; infrastructure_score:float; aggregate_confidence:float; residual_risk:float
    evidence_digest:str; confidence_digest:str; approved_by:str|None=None; version:int=1

class RecoveryStabilityObservationService:
    def __init__(self):
        self._records:dict[tuple[str,str],StabilityRecord]={}; self._sources:set[tuple[str,str]]=set(); self._ops:set[tuple[str,str]]=set(); self._audit=[]

    def status(self):
        return {"module":"recovery-stability-observation-primary-route-confidence-governance","version":"21.142","external_execution_enabled":False,"autonomous_route_mutation_enabled":False,"human_approval_required":True,"risk_brain_authoritative":True}

    def create(self, *,record_id:str,workspace_id:str,source_key:str,recovery_attestation_id:str,recovery_attestation_digest:str,recovery_attestation_state:str,operation:str,target:str,samples:list[StabilitySample],max_latency_ms:float=1500,min_reconciliation:float=.95,upstream_risk_brain_blocked:bool=False,requested_by:str="system"):
        key=(workspace_id,source_key)
        if key in self._sources: raise ValueError("duplicate source_key for workspace")
        if recovery_attestation_state!="attested": raise ValueError("approved recovery attestation required")
        if not samples: raise ValueError("at least one stability sample required")
        blocked=operation in PROTECTED_OPERATIONS or upstream_risk_brain_blocked
        availability=mean(1.0 if s.primary_available else 0.0 for s in samples)
        latency=mean(max(0.0,1-(s.latency_ms/max_latency_ms)) for s in samples)
        reconciliation=mean(1.0 if s.receipt_reconciliation>=min_reconciliation else s.receipt_reconciliation/min_reconciliation for s in samples)
        infra=mean((int(s.worker_heartbeat_ok)+int(s.gateway_healthy)+int(s.adapter_healthy))/3 for s in samples)
        trust=mean(max(0,min(1,s.confidence))*max(0,min(1,s.freshness)) for s in samples)
        aggregate=round(mean([availability,latency,reconciliation,infra])*trust,4)
        residual=round(1-aggregate,4)
        state="blocked" if blocked else ("observation-ready" if aggregate>=.85 else "degraded")
        evidence_digest=_digest([asdict(s) for s in samples])
        confidence_digest=_digest({"attestation":recovery_attestation_digest,"operation":operation,"target":target,"scores":[availability,latency,reconciliation,infra,aggregate,residual]})
        r=StabilityRecord(record_id,workspace_id,source_key,recovery_attestation_id,recovery_attestation_digest,operation,target,state,len(samples),round(availability,4),round(latency,4),round(reconciliation,4),round(infra,4),aggregate,residual,evidence_digest,confidence_digest)
        self._records[(workspace_id,record_id)]=r; self._sources.add(key); self._audit.append({"workspace_id":workspace_id,"record_id":record_id,"action":"create","actor":requested_by,"digest":confidence_digest}); return r

    def get(self,ws,rid):
        if (ws,rid) not in self._records: raise KeyError("record not found")
        return self._records[(ws,rid)]
    def list(self,ws): return [r for (w,_),r in self._records.items() if w==ws]

    def act(self,ws,rid,action,actor,operation_id,reason=None):
        if (ws,operation_id) in self._ops: raise ValueError("operation replay detected")
        r=self.get(ws,rid)
        if r.state=="blocked" and action not in {"revoke","archive"}: raise ValueError("risk brain hard block")
        if action=="submit-review": new="review-required"
        elif action=="approve":
            if r.state!="review-required": raise ValueError("review required before approval")
            if r.aggregate_confidence<.85: raise ValueError("primary route confidence below threshold")
            new="approved"
        elif action=="close-episode":
            if r.state!="approved": raise ValueError("human approval required before closing episode")
            new="stable"
        elif action=="revoke": new="revoked"
        elif action=="archive": new="archived"
        else: raise ValueError("unsupported action")
        r.state=new; r.approved_by=actor if action=="approve" else r.approved_by; r.version+=1
        self._ops.add((ws,operation_id)); self._audit.append({"workspace_id":ws,"record_id":rid,"action":action,"actor":actor,"operation_id":operation_id,"reason":reason}); return r

    def audit(self,ws): return [e for e in self._audit if e["workspace_id"]==ws]

recovery_stability_observation_service=RecoveryStabilityObservationService()
