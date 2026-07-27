from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class FailoverPermitState(str, Enum):
    BLOCKED = "blocked"
    AUTHORIZED = "authorized"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ISSUED = "issued"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class FailoverPermitCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    failover_authorization_id: str = Field(min_length=1)
    failover_authorization_digest: str = Field(min_length=8)
    dispatch_plan_id: str = Field(min_length=1)
    dispatch_plan_digest: str = Field(min_length=8)
    operation: str = Field(min_length=1)
    target: str = Field(min_length=1)
    standby_adapter_id: str = Field(min_length=1)
    standby_worker_id: str = Field(min_length=1)
    gateway_id: str = Field(min_length=1)
    sandbox_policy_digest: str = Field(min_length=8)
    gateway_policy_digest: str = Field(min_length=8)
    worker_policy_digest: str = Field(min_length=8)
    permit_ttl_seconds: int = Field(default=120, ge=15, le=900)
    upstream_risk_brain_blocked: bool = False
    failover_authorized: bool = True


class FailoverPermitRecord(BaseModel):
    permit_id: str
    workspace_id: str
    source_key: str
    state: FailoverPermitState
    failover_authorization_id: str
    failover_authorization_digest: str
    dispatch_plan_id: str
    dispatch_plan_digest: str
    operation: str
    target: str
    standby_adapter_id: str
    standby_worker_id: str
    gateway_id: str
    sandbox_policy_digest: str
    gateway_policy_digest: str
    worker_policy_digest: str
    issued_at: Optional[str] = None
    expires_at: Optional[str] = None
    consumed_at: Optional[str] = None
    permit_token_digest: Optional[str] = None
    handoff_digest: str
    approved_by: Optional[str] = None
    version: int = 1


class FailoverPermitAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None


class FailoverPermitConsume(BaseModel):
    workspace_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    failover_authorization_digest: str = Field(min_length=8)
    standby_adapter_id: str = Field(min_length=1)
    standby_worker_id: str = Field(min_length=1)
    gateway_id: str = Field(min_length=1)
