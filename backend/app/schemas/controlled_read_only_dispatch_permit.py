from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class DispatchPermitState(str, Enum):
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ISSUED = "issued"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class DispatchPermitCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    authorization_chain_record_id: str = Field(min_length=1, max_length=160)
    authorization_chain_digest: str = Field(min_length=8, max_length=256)
    authorization_chain_state: str = Field(pattern="^eligible$")
    operation: str = Field(min_length=1, max_length=160)
    target: str = Field(min_length=1, max_length=2048)
    method: str = Field(default="GET", pattern="^(GET|HEAD)$")
    adapter_id: str = Field(min_length=1, max_length=160)
    worker_id: str = Field(min_length=1, max_length=160)
    gateway_record_id: str = Field(min_length=1, max_length=160)
    dispatch_token_digest: str = Field(min_length=8, max_length=256)
    ttl_seconds: int = Field(default=120, ge=5, le=300)
    max_uses: int = Field(default=1, ge=1, le=1)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)
    risk_brain_hard_blocked: bool = False

    @model_validator(mode="after")
    def validate_read_only_permit(self):
        if self.method not in {"GET", "HEAD"}:
            raise ValueError("one-time dispatch permits are read-only")
        if self.max_uses != 1:
            raise ValueError("permit must be single-use")
        return self


class DispatchPermitRecord(BaseModel):
    permit_id: str
    workspace_id: str
    source_key: str
    state: DispatchPermitState
    authorization_chain_record_id: str
    authorization_chain_digest: str
    operation: str
    target: str
    method: str
    adapter_id: str
    worker_id: str
    gateway_record_id: str
    dispatch_token_digest: str
    permit_token_digest: Optional[str] = None
    issued_at: Optional[str] = None
    expires_at: Optional[str] = None
    consumed_at: Optional[str] = None
    approved_by: Optional[str] = None
    issued_by: Optional[str] = None
    consumed_by: Optional[str] = None
    risk_flags: List[str] = Field(default_factory=list)
    version: int = 1


class DispatchPermitAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None


class DispatchPermitConsume(BaseModel):
    workspace_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    permit_token_digest: str = Field(min_length=8)
    authorization_chain_digest: str = Field(min_length=8)
    dispatch_token_digest: str = Field(min_length=8)
    adapter_id: str = Field(min_length=1)
    worker_id: str = Field(min_length=1)
