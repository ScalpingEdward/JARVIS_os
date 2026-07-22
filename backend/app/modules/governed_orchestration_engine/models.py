from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrchestrationState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    PLANNING = "planning"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class OrchestrationCommand(str, Enum):
    APPROVE = "approve"
    DISPATCH = "dispatch"
    COMPLETE = "complete"
    FAIL = "fail"
    CANCEL = "cancel"
    ARCHIVE = "archive"


class WorkflowStep(BaseModel):
    step_id: str = Field(..., min_length=1, max_length=120)
    module: str = Field(..., min_length=1, max_length=120)
    action: str = Field(..., min_length=1, max_length=120)
    depends_on: List[str] = Field(default_factory=list, max_length=50)
    timeout_seconds: int = Field(default=30, ge=1, le=3600)
    retry_limit: int = Field(default=0, ge=0, le=10)
    requires_human_approval: bool = False

    @field_validator("depends_on")
    @classmethod
    def unique_dependencies(cls, value: List[str]) -> List[str]:
        if len(value) != len(set(value)):
            raise ValueError("depends_on must not contain duplicates")
        return value


class OrchestrationCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=120)
    source_key: str = Field(..., min_length=1, max_length=240)
    strategy_policy_record_id: str = Field(..., min_length=1, max_length=120)
    workflow_name: str = Field(..., min_length=1, max_length=160)
    steps: List[WorkflowStep] = Field(..., min_length=1, max_length=100)
    max_parallel_steps: int = Field(default=1, ge=1, le=20)
    upstream_evidence_verified: bool = False
    active_policy_verified: bool = False
    risk_brain_blocked: bool = False


class OrchestrationAction(BaseModel):
    command: OrchestrationCommand
    actor: str = Field(..., min_length=1, max_length=120)
    approval_token: Optional[str] = Field(default=None, max_length=240)
    dispatch_receipt: Optional[str] = Field(default=None, max_length=240)
    completion_receipt: Optional[str] = Field(default=None, max_length=240)
    reason: Optional[str] = Field(default=None, max_length=1000)


class OrchestrationPlan(BaseModel):
    ordered_step_ids: List[str]
    execution_batches: List[List[str]]
    approval_required_steps: List[str]
    total_timeout_seconds: int
    warnings: List[str] = Field(default_factory=list)


class OrchestrationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    strategy_policy_record_id: str
    workflow_name: str
    steps: List[WorkflowStep]
    max_parallel_steps: int
    state: OrchestrationState
    plan: Optional[OrchestrationPlan] = None
    approval_token: Optional[str] = None
    dispatch_receipt: Optional[str] = None
    completion_receipt: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    record_id: str
    action: str
    actor: str
    from_state: Optional[OrchestrationState] = None
    to_state: OrchestrationState
    details: Dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
