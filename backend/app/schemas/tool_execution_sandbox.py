from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class SandboxExecutionState(str, Enum):
    DRAFT = "draft"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed-out"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class SideEffectLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolExecutionRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    agent_id: str = Field(min_length=1, max_length=160)
    task_id: str = Field(min_length=1, max_length=160)
    tool_name: str = Field(min_length=1, max_length=160)
    operation: str = Field(min_length=1, max_length=160)
    arguments: Dict[str, Any] = Field(default_factory=dict)
    permission_scopes: List[str] = Field(default_factory=list)
    allowed_operations: List[str] = Field(default_factory=list)
    denied_operations: List[str] = Field(default_factory=list)
    side_effect_level: SideEffectLevel = SideEffectLevel.NONE
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    max_calls: int = Field(default=1, ge=1, le=100)
    budget_units: float = Field(default=1.0, ge=0.0, le=1000.0)
    requires_human_approval: bool = True
    dry_run: bool = True
    kill_switch_armed: bool = True
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_contract(self):
        if self.operation in self.denied_operations:
            raise ValueError("operation explicitly denied")
        if self.allowed_operations and self.operation not in self.allowed_operations:
            raise ValueError("operation not present in allow-list")
        if self.side_effect_level in {SideEffectLevel.HIGH, SideEffectLevel.CRITICAL} and not self.requires_human_approval:
            raise ValueError("high-risk operations require human approval")
        if not self.kill_switch_armed:
            raise ValueError("kill switch must be armed")
        return self


class ToolExecutionReceipt(BaseModel):
    receipt_id: str
    record_id: str
    tool_name: str
    operation: str
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    call_count: int = 0
    budget_used: float = 0.0
    output_digest: Optional[str] = None
    error: Optional[str] = None
    dry_run: bool = True


class ToolExecutionRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: SandboxExecutionState
    request: ToolExecutionRequest
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    authorization_token_id: Optional[str] = None
    receipt: Optional[ToolExecutionReceipt] = None
    version: int = 1


class ToolExecutionAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None


class ToolExecutionResult(BaseModel):
    workspace_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    call_count: int = Field(default=1, ge=0)
    budget_used: float = Field(default=0.0, ge=0.0)
    output_digest: Optional[str] = None
    error: Optional[str] = None
