from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator

class DispatchPlanState(str, Enum):
    BLOCKED="blocked"; DRAFT="draft"; REVIEW_REQUIRED="review-required"; APPROVED="approved"; READY="ready"; DEGRADED="degraded"; FAILOVER_REQUIRED="failover-required"; SUSPENDED="suspended"; REVOKED="revoked"; ARCHIVED="archived"

class DispatchCandidate(BaseModel):
    adapter_id:str=Field(min_length=1); worker_id:str=Field(min_length=1); selection_record_id:str=Field(min_length=1); selection_digest:str=Field(min_length=1)
    trust_score:float=Field(ge=0,le=1); reliability:float=Field(ge=0,le=1); latency_quality:float=Field(ge=0,le=1); confidence:float=Field(ge=0,le=1); freshness:float=Field(ge=0,le=1)
    capability_match:bool=True; permission_match:bool=True; sandbox_match:bool=True; policy_match:bool=True; active:bool=True; risk_brain_blocked:bool=False

class FailoverPolicy(BaseModel):
    max_primary_failures:int=Field(default=1,ge=1,le=10); max_latency_ms:int=Field(default=5000,ge=1); min_receipt_reconciliation:float=Field(default=.95,ge=0,le=1)
    require_worker_heartbeat:bool=True; require_gateway_health:bool=True; allow_standby_failover:bool=True

class DispatchPlanCreate(BaseModel):
    workspace_id:str=Field(min_length=1); source_key:str=Field(min_length=1); requested_by:str=Field(min_length=1)
    operation:str=Field(min_length=1); target:str=Field(min_length=1); authorization_chain_id:str=Field(min_length=1); authorization_chain_digest:str=Field(min_length=1)
    candidates:List[DispatchCandidate]=Field(min_length=2); failover_policy:FailoverPolicy=Field(default_factory=FailoverPolicy)
    @model_validator(mode="after")
    def unique_pairs(self):
        pairs=[(c.adapter_id,c.worker_id) for c in self.candidates]
        if len(pairs)!=len(set(pairs)): raise ValueError("duplicate adapter/worker candidate")
        return self

class RankedDispatchCandidate(BaseModel):
    adapter_id:str; worker_id:str; score:float=Field(ge=0,le=1); rank:int=Field(ge=1); eligible:bool; reasons:List[str]=Field(default_factory=list)

class DispatchPlanRecord(BaseModel):
    record_id:str; workspace_id:str; source_key:str; operation:str; target:str; authorization_chain_id:str; authorization_chain_digest:str; state:DispatchPlanState
    primary:Optional[RankedDispatchCandidate]=None; standby:Optional[RankedDispatchCandidate]=None; ranked_candidates:List[RankedDispatchCandidate]=Field(default_factory=list)
    failover_policy:FailoverPolicy; plan_digest:str; risk_flags:List[str]=Field(default_factory=list); approved_by:Optional[str]=None; version:int=1

class DispatchPlanAction(BaseModel):
    workspace_id:str=Field(min_length=1); action:str=Field(min_length=1); actor:str=Field(min_length=1); operation_id:str=Field(min_length=1); reason:Optional[str]=None
