from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator

class OutcomeValidationState(str, Enum):
    BLOCKED='blocked'; EVIDENCE_READY='evidence-ready'; REVIEW_REQUIRED='review-required'; VERIFIED='verified'; APPROVED='approved'; ATTESTED='attested'; MISMATCH='mismatch'; REVOKED='revoked'; ARCHIVED='archived'

class PostconditionEvidence(BaseModel):
    key:str=Field(min_length=1); expected:str=Field(min_length=1); observed:str=Field(min_length=1); passed:bool

class SideEffectAttestation(BaseModel):
    write_detected:bool=False; credential_mutation_detected:bool=False; permission_mutation_detected:bool=False; fund_movement_detected:bool=False; order_submission_detected:bool=False; trading_execution_detected:bool=False; repository_mutation_detected:bool=False; external_side_effect_notes:List[str]=Field(default_factory=list)

class OutcomeValidationCreate(BaseModel):
    workspace_id:str=Field(min_length=1); source_key:str=Field(min_length=1); requested_by:str=Field(min_length=1)
    reconciliation_record_id:str=Field(min_length=1); reconciliation_digest:str=Field(min_length=16)
    permit_id:str=Field(min_length=1); authorization_chain_digest:str=Field(min_length=16); receipt_digest:str=Field(min_length=16); response_digest:str=Field(min_length=16)
    operation:str=Field(min_length=1); target:str=Field(min_length=1); method:str=Field(min_length=1)
    receipt_status:str=Field(min_length=1); postconditions:List[PostconditionEvidence]=Field(default_factory=list); side_effects:SideEffectAttestation
    upstream_risk_brain_blocked:bool=False; human_review_required:bool=True
    @model_validator(mode='after')
    def validate_read_only(self):
        if self.method.upper() not in {'GET','HEAD'}: raise ValueError('v21.131 validates read-only GET/HEAD outcomes only')
        return self

class OutcomeValidationRecord(BaseModel):
    record_id:str; workspace_id:str; source_key:str; state:OutcomeValidationState
    reconciliation_record_id:str; reconciliation_digest:str; permit_id:str; authorization_chain_digest:str; receipt_digest:str; response_digest:str
    operation:str; target:str; method:str; receipt_status:str; postconditions:List[PostconditionEvidence]; side_effects:SideEffectAttestation
    validation_score:float=Field(ge=0,le=1); side_effect_free:bool; risk_flags:List[str]=Field(default_factory=list); attestation_digest:str
    approved_by:Optional[str]=None; version:int=1

class OutcomeValidationAction(BaseModel):
    workspace_id:str=Field(min_length=1); action:str=Field(min_length=1); actor:str=Field(min_length=1); operation_id:str=Field(min_length=1); reason:Optional[str]=None
