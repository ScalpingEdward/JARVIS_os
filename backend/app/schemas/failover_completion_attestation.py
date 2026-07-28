from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class FailoverCompletionState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_READY = "evidence-ready"
    RECONCILED = "reconciled"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ATTESTED = "attested"
    MISMATCH = "mismatch"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class StandbyExecutionReceipt(BaseModel):
    status: str = Field(min_length=1)
    response_digest: str = Field(min_length=8)
    receipt_digest: str = Field(min_length=8)
    duration_ms: float = Field(ge=0)
    response_bytes: int = Field(ge=0)
    method: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    worker_id: str = Field(min_length=1)
    gateway_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    target: str = Field(min_length=1)
    write_side_effect_detected: bool = False
    credential_mutation_detected: bool = False
    permission_mutation_detected: bool = False
    fund_movement_detected: bool = False
    order_submission_detected: bool = False
    trading_execution_detected: bool = False


class FailoverCompletionCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    failover_permit_id: str = Field(min_length=1)
    failover_permit_digest: str = Field(min_length=8)
    failover_authorization_id: str = Field(min_length=1)
    failover_authorization_digest: str = Field(min_length=8)
    dispatch_plan_id: str = Field(min_length=1)
    dispatch_plan_digest: str = Field(min_length=8)
    standby_adapter_id: str = Field(min_length=1)
    standby_worker_id: str = Field(min_length=1)
    gateway_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    target: str = Field(min_length=1)
    permit_consumed: bool
    upstream_risk_brain_blocked: bool = False
    receipt: StandbyExecutionReceipt


class FailoverCompletionRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: FailoverCompletionState
    failover_permit_id: str
    failover_permit_digest: str
    failover_authorization_id: str
    failover_authorization_digest: str
    dispatch_plan_id: str
    dispatch_plan_digest: str
    standby_adapter_id: str
    standby_worker_id: str
    gateway_id: str
    operation: str
    target: str
    receipt_digest: str
    response_digest: str
    reconciliation_digest: str
    side_effect_safe: bool
    bindings_valid: bool
    approved_by: Optional[str] = None
    version: int = 1


class FailoverCompletionAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
