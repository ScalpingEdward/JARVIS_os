from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator

class SelectionState(str, Enum):
    BLOCKED='blocked'; EVIDENCE_READY='evidence-ready'; REVIEW_REQUIRED='review-required'; APPROVED='approved'; READY='ready'; REVOKED='revoked'; ARCHIVED='archived'

class ExecutionCandidate(BaseModel):
    adapter_id:str=Field(min_length=1); worker_id:str=Field(min_length=1); capability_match:float=Field(ge=0,le=1); permission_match:float=Field(ge=0,le=1); sandbox_match:float=Field(ge=0,le=1); policy_match:float=Field(ge=0,le=1); trust_score:float=Field(ge=0,le=1); reliability:float=Field(ge=0,le=1); latency_quality:float=Field(ge=0,le=1); freshness:float=Field(ge=0,le=1); confidence:float=Field(ge=0,le=1); active:bool=True; risk_brain_blocked:bool=False

class SelectionCreate(BaseModel):
    workspace_id:str=Field(min_length=1); source_key:str=Field(min_length=1); requested_by:str=Field(min_length=1); operation:str=Field(min_length=1); target:str=Field(min_length=1); candidates:List[ExecutionCandidate]=Field(min_length=1); min_trust:float=Field(default=.75,ge=0,le=1); min_confidence:float=Field(default=.70,ge=0,le=1)
    @model_validator(mode='after')
    def unique_candidates(self):
        keys=[(c.adapter_id,c.worker_id) for c in self.candidates]
        if len(keys)!=len(set(keys)): raise ValueError('duplicate adapter/worker candidate')
        return self

class RankedCandidate(BaseModel):
    adapter_id:str; worker_id:str; selection_score:float=Field(ge=0,le=1); eligible:bool; reasons:List[str]=Field(default_factory=list)

class SelectionRecord(BaseModel):
    record_id:str; workspace_id:str; source_key:str; operation:str; target:str; state:SelectionState; ranked_candidates:List[RankedCandidate]; selected_adapter_id:Optional[str]=None; selected_worker_id:Optional[str]=None; selection_digest:str; risk_flags:List[str]=Field(default_factory=list); approved_by:Optional[str]=None; version:int=1

class SelectionAction(BaseModel):
    workspace_id:str=Field(min_length=1); action:str=Field(min_length=1); actor:str=Field(min_length=1); operation_id:str=Field(min_length=1); reason:Optional[str]=None
