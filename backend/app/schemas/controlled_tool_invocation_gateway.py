from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ToolInvocationState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    AUTHORIZED = "authorized"
    DISPATCH_READY = "dispatch-ready"
    DISPATCHED = "dispatched"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed-out"
    CANCELLED = "cancelled"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class ToolInvocationRequest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    task_id: str = Field(min_length=1, max_length=160)
    sandbox_record_id: str = Field(min_length=1, max_length=160)
    adapter_id: str = Field(min_length=1, max_length=160)
    tool_name: str = Field(min_length=1, max_length=160)
    operation: str = Field(min_length=1, max_length=160)
    permission_scopes: List[str] = Field(default_factory=list)
    data_domains: List[str] = Field(default_factory=list)
    target_host: Optional[str] = Field(default=None, max_length=255)
    arguments: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    estimated_cost: float = Field(default=0.0, ge=0.0)
    side_effect_level: str = Field(default="read-only")
    human_approval_required: bool = True
    dry_run_verified: bool = True


class ToolInvocationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    invocation: ToolInvocationRequest
    allowed_tools: List[str] = Field(min_length=1)
    allowed_operations: List[str] = Field(min_length=1)
    allowed_hosts: List[str] = Field(default_factory=list)
    denied_operations: List[str] = Field(default_factory=list)
    max_cost: float = Field(default=25.0, ge=0.0)
    max_timeout_seconds: int = Field(default=120, ge=1, le=300)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_contract(self):
        if self.invocation.tool_name not in self.allowed_tools:
            raise ValueError("tool not in gateway allow-list")
        if self.invocation.operation not in self.allowed_operations:
            raise ValueError("operation not in gateway allow-list")
        return self


class ToolInvocationScores(BaseModel):
    policy_coverage: float = Field(ge=0.0, le=1.0)
    authorization_assurance: float = Field(ge=0.0, le=1.0)
    adapter_binding_assurance: float = Field(ge=0.0, le=1.0)
    side_effect_assurance: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)


class ToolInvocationRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: ToolInvocationState
    invocation: ToolInvocationRequest
    scores: ToolInvocationScores
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    authorized_by: Optional[str] = None
    dispatch_token: Optional[str] = None
    result_status: Optional[str] = None
    result_digest: Optional[str] = None
    version: int = 1


class ToolInvocationAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None


class ToolInvocationResult(BaseModel):
    workspace_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    status: str = Field(pattern="^(succeeded|failed|timed-out)$")
    output_digest: str = Field(min_length=1, max_length=256)
    duration_ms: int = Field(ge=0)
    cost: float = Field(default=0.0, ge=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
