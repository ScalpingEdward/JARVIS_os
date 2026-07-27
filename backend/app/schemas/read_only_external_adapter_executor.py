from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ReadOnlyExecutorState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    AUTHORIZED = "authorized"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed-out"
    CANCELLED = "cancelled"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class ReadOnlyExecutionRequest(BaseModel):
    worker_record_id: str = Field(min_length=1, max_length=160)
    gateway_record_id: str = Field(min_length=1, max_length=160)
    dispatch_token_digest: str = Field(min_length=8, max_length=256)
    worker_id: str = Field(min_length=1, max_length=160)
    adapter_id: str = Field(min_length=1, max_length=160)
    tool_name: str = Field(min_length=1, max_length=160)
    operation: str = Field(min_length=1, max_length=160)
    target_host: str = Field(min_length=1, max_length=255)
    target_path: str = Field(default="/", min_length=1, max_length=2048)
    method: str = Field(default="GET", pattern="^(GET|HEAD)$")
    query: Dict[str, str] = Field(default_factory=dict)
    headers: Dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=20, ge=1, le=60)
    max_response_bytes: int = Field(default=1_048_576, ge=1, le=10_485_760)
    follow_redirects: bool = False
    side_effect_level: str = Field(default="read-only")


class ReadOnlyExecutionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    request: ReadOnlyExecutionRequest
    egress_allow_hosts: List[str] = Field(min_length=1)
    pinned_hosts: List[str] = Field(min_length=1)
    allowed_operations: List[str] = Field(min_length=1)
    denied_path_prefixes: List[str] = Field(default_factory=lambda: ["/admin", "/write", "/delete"])
    require_https: bool = True
    require_human_approval: bool = True
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_read_only_contract(self):
        r = self.request
        if r.method not in {"GET", "HEAD"}:
            raise ValueError("only GET/HEAD permitted")
        if r.side_effect_level != "read-only":
            raise ValueError("executor accepts read-only requests only")
        if r.target_host not in self.egress_allow_hosts:
            raise ValueError("target host not in egress allow-list")
        if r.target_host not in self.pinned_hosts:
            raise ValueError("target host not pinned")
        if r.operation not in self.allowed_operations:
            raise ValueError("operation not allowed")
        if any(r.target_path.startswith(prefix) for prefix in self.denied_path_prefixes):
            raise ValueError("target path denied")
        return self


class ReadOnlyExecutionScores(BaseModel):
    egress_assurance: float = Field(ge=0.0, le=1.0)
    host_pinning_assurance: float = Field(ge=0.0, le=1.0)
    response_limit_assurance: float = Field(ge=0.0, le=1.0)
    read_only_assurance: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)


class ReadOnlyExecutionRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: ReadOnlyExecutorState
    request: ReadOnlyExecutionRequest
    scores: ReadOnlyExecutionScores
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    authorized_by: Optional[str] = None
    receipt_digest: Optional[str] = None
    response_digest: Optional[str] = None
    response_bytes: Optional[int] = None
    version: int = 1


class ReadOnlyExecutionAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None


class ReadOnlyExecutionResult(BaseModel):
    workspace_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    worker_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    status: str = Field(pattern="^(succeeded|failed|timed-out)$")
    http_status: Optional[int] = Field(default=None, ge=100, le=599)
    response_digest: str = Field(min_length=1, max_length=256)
    response_bytes: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    metadata: Dict[str, str] = Field(default_factory=dict)
