from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class ProposalState(str, Enum):
    BLOCKED="blocked"; REVIEW_REQUIRED="review-required"; APPROVED="approved"; AUTHORIZED="authorized"; READY="ready"; REJECTED="rejected"; REVOKED="revoked"; ARCHIVED="archived"

class ProposedAction(BaseModel):
    action_id:str=Field(min_length=1); target:str=Field(min_length=1); operation:str=Field(min_length=1); rationale:str=Field(min_length=1); expected_outcome:str=Field(min_length=1)
    preconditions:List[str]=Field(default_factory=list); postconditions:List[str]=Field(default_factory=list); rollback_plan:List[str]=Field(default_factory=list)
    blast_radius:float=Field(default=.2,ge=0,le=1); reversibility:float=Field(default=1,ge=0,le=1); observability:float=Field(default=1,ge=0,le=1); validation_readiness:float=Field(default=1,ge=0,le=1)

class ProposalCreate(BaseModel):
    workspace_id:str=Field(min_length=1); source_key:str=Field(min_length=1); decision_record_id:str=Field(min_length=1); decision_state:str=Field(min_length=1); decision_packet_digest:str=Field(min_length=8); requested_by:str=Field(min_length=1); actions:List[ProposedAction]=Field(min_length=1); decision_confidence:float=Field(ge=0,le=1); residual_risk:float=Field(ge=0,le=1); criticality:float=Field(default=.5,ge=0,le=1)

class ProposalScores(BaseModel):
    reversibility:float=Field(ge=0,le=1); observability:float=Field(ge=0,le=1); validation_readiness:float=Field(ge=0,le=1); blast_radius_assurance:float=Field(ge=0,le=1); aggregate_assurance:float=Field(ge=0,le=1)

class ProposalRecord(BaseModel):
    record_id:str; workspace_id:str; source_key:str; decision_record_id:str; state:ProposalState; proposal_digest:str; scores:ProposalScores; risk_flags:List[str]=Field(default_factory=list); approved_by:Optional[str]=None; authorized_by:Optional[str]=None; executable:bool=False; version:int=1

class ProposalAction(BaseModel):
    workspace_id:str=Field(min_length=1); action:str=Field(min_length=1); actor:str=Field(min_length=1); operation_id:str=Field(min_length=1); reason:Optional[str]=None
