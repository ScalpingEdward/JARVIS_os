from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DispatchReconciliationState(str, Enum):
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    HANDOFF_READY = "handoff-ready"
    PERMIT_CONSUMED = "permit-consumed"
    DISPATCHED = "dispatched"
    RECEIPT_RECEIVED = "receipt-received"
    RECONCILED = "reconciled"
    FAILED = "failed"
    MISMATCH = "mismatch"
    REVOKED = "revoked"
    ARCHIVED = "archived"
    BLOCKED = "blocked"


class DispatchHandoffCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    permit_id: str = Field(min_length=1)
    permit_token_digest: str = Field(min_length=16)
    authorization_chain_record_id: str = Field(min_length=1)
    authorization_chain_digest: str = Field(min_length=16)
    gateway_record_id: str = Field(min_length=1)
    gateway_dispatch_token_digest: str = Field(min_length=16)
    worker_record_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    target: str = Field(min_length=1)
    method: str = Field(default="GET")
    human_approved: bool = False
    permit_eligible: bool = False
    permit_issued: bool = False
    permit_expired: bool = False
    upstream_risk_brain_blocked: bool = False


class DispatchReconciliationAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None


class DispatchReceipt(BaseModel):
    workspace_id: str = Field(min_length=1)
    permit_id: str = Field(min_length=1)
    permit_token_digest: str = Field(min_length=16)
    authorization_chain_digest: str = Field(min_length=16)
    gateway_dispatch_token_digest: str = Field(min_length=16)
    worker_record_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    target: str = Field(min_length=1)
    status_code: int = Field(ge=100, le=599)
    response_digest: str = Field(min_length=16)
    receipt_digest: str = Field(min_length=16)
    duration_ms: int = Field(ge=0)
    response_bytes: int = Field(ge=0)


class DispatchReconciliationRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: DispatchReconciliationState
    permit_id: str
    authorization_chain_record_id: str
    gateway_record_id: str
    worker_record_id: str
    adapter_id: str
    operation: str
    target: str
    handoff_digest: str
    reconciliation_digest: Optional[str] = None
    response_digest: Optional[str] = None
    receipt_digest: Optional[str] = None
    mismatch_reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1
