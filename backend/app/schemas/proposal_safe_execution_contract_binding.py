from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class BindingState(str, Enum):
    BLOCKED='blocked'; REVIEW_REQUIRED='review-required'; APPROVED='approved'; BOUND='bound'; READY='ready'; REVOKED='revoked'; ARCHIVED='archived'

class ExecutionBindingCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    proposal_record_id: str = Field(min_length=1)
    proposal_digest: str = Field(min_length=8)
    proposal_state: str = Field(min_length=1)
    proposal_authorized: bool = False
    safe_execution_contract_id: str = Field(min_length=1)
    safe_execution_contract_digest: str = Field(min_length=8)
    sandbox_policy_id: str = Field(min_length=1)
    adapter_policy_id: str = Field(min_length=1)
    gateway_policy_id: str = Field(min_length=1)
    worker_policy_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    target: str = Field(min_length=1)
    human_authorization_required: bool = True
    execution_enabled: bool = False
    criticality: float = Field(default=.5, ge=0, le=1)

class ExecutionBindingRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: BindingState
    binding_digest: str
    proposal_record_id: str
    safe_execution_contract_id: str
    operation: str
    target: str
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    bound_by: Optional[str] = None
    execution_enabled: bool = False
    version: int = 1

class ExecutionBindingAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
