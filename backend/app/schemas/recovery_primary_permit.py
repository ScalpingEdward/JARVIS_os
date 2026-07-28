from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RecoveryPermitState(str, Enum):
    BLOCKED = "blocked"
    PLAN_READY = "plan-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ISSUED = "issued"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RecoveryPermitCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    recovery_plan_id: str = Field(min_length=1)
    recovery_plan_digest: str = Field(min_length=8)
    recovery_readiness_digest: str = Field(min_length=8)
    dispatch_plan_digest: str = Field(min_length=8)
    operation: str = Field(min_length=1)
    target: str = Field(min_length=1)
    primary_adapter_id: str = Field(min_length=1)
    primary_worker_id: str = Field(min_length=1)
    gateway_id: str = Field(min_length=1)
    sandbox_policy_digest: str = Field(min_length=8)
    gateway_policy_digest: str = Field(min_length=8)
    worker_policy_digest: str = Field(min_length=8)
    plan_state: str = Field(default="ready")
    upstream_risk_brain_blocked: bool = False
    ttl_seconds: int = Field(default=300, ge=30, le=3600)


class RecoveryPermitRecord(BaseModel):
    permit_id: str
    workspace_id: str
    source_key: str
    state: RecoveryPermitState
    recovery_plan_id: str
    recovery_plan_digest: str
    recovery_readiness_digest: str
    dispatch_plan_digest: str
    operation: str
    target: str
    primary_adapter_id: str
    primary_worker_id: str
    gateway_id: str
    sandbox_policy_digest: str
    gateway_policy_digest: str
    worker_policy_digest: str
    permit_token_digest: Optional[str] = None
    binding_digest: str
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    consumed_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    version: int = 1


class RecoveryPermitAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None


class RecoveryPermitConsume(BaseModel):
    workspace_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    permit_token: str = Field(min_length=16)
    recovery_plan_digest: str = Field(min_length=8)
    primary_adapter_id: str = Field(min_length=1)
    primary_worker_id: str = Field(min_length=1)
    gateway_id: str = Field(min_length=1)
