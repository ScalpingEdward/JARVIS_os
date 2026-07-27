from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator

class ExperimentState(str, Enum):
    BLOCKED="blocked"; EVIDENCE_READY="evidence-ready"; ASSESSED="assessed"; REVIEW_REQUIRED="review-required"; APPROVED="approved"; VALIDATED="validated"; REJECTED="rejected"; ARCHIVED="archived"

class ExperimentObservation(BaseModel):
    candidate_id:str=Field(min_length=1,max_length=160)
    baseline_score:float=Field(ge=0,le=1); candidate_score:float=Field(ge=0,le=1)
    reliability_score:float=Field(ge=0,le=1); latency_score:float=Field(ge=0,le=1); cost_score:float=Field(ge=0,le=1); resource_score:float=Field(ge=0,le=1)
    shadow_coverage:float=Field(ge=0,le=1); ab_evidence:float=Field(ge=0,le=1); statistical_confidence:float=Field(ge=0,le=1)
    rollback_readiness:float=Field(ge=0,le=1); regression_count:int=Field(default=0,ge=0); criticality:float=Field(default=.5,ge=0,le=1)

class ExperimentCreate(BaseModel):
    workspace_id:str=Field(min_length=1); source_key:str=Field(min_length=1); requested_by:str=Field(min_length=1)
    observations:List[ExperimentObservation]=Field(min_length=1)
    min_gain:float=Field(default=.03,ge=0,le=1); min_confidence:float=Field(default=.90,ge=0,le=1); min_rollback:float=Field(default=.90,ge=0,le=1); max_residual_risk:float=Field(default=.30,ge=0,le=1)
    @model_validator(mode="after")
    def unique_candidates(self):
        ids=[o.candidate_id for o in self.observations]
        if len(ids)!=len(set(ids)): raise ValueError("duplicate candidate observation")
        return self

class ExperimentDisposition(BaseModel):
    candidate_id:str; expected_gain:float; assurance:float=Field(ge=0,le=1); residual_risk:float=Field(ge=0,le=1); signal:str; required_actions:List[str]=Field(default_factory=list)

class ExperimentRecord(BaseModel):
    record_id:str; workspace_id:str; source_key:str; state:ExperimentState; dispositions:List[ExperimentDisposition]; risk_flags:List[str]=Field(default_factory=list); approved_by:Optional[str]=None; version:int=1

class ExperimentAction(BaseModel):
    workspace_id:str=Field(min_length=1); action:str=Field(min_length=1); actor:str=Field(min_length=1); operation_id:str=Field(min_length=1); reason:Optional[str]=None
