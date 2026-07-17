from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class RiskClass(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class PolicyState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class RequestState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class DecisionType(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class ExceptionState(str, Enum):
    REQUESTED = "requested"
    GRANTED = "granted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"


class PolicyCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    policy_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=5000)
    target_modules: list[str] = Field(default_factory=list, max_length=300)
    target_actions: list[str] = Field(default_factory=list, max_length=300)
    effect: PolicyEffect
    minimum_risk: RiskClass = RiskClass.LOW
    required_approvals: int = Field(default=1, ge=1, le=20)
    require_distinct_approvers: bool = True
    approval_ttl_minutes: int = Field(default=60, ge=1, le=10080)
    priority: int = Field(default=100, ge=0, le=100000)
    conditions: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_external_enforcement: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "PolicyCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_external_enforcement:
            raise ValueError("automatic external enforcement is disabled in v9.0")
        return self


class PolicyRecord(PolicyCreate):
    id: UUID = Field(default_factory=uuid4)
    state: PolicyState = PolicyState.DRAFT
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PolicyMutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=2000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "PolicyMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class EvaluationRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    source_module: str = Field(min_length=1, max_length=160)
    action: str = Field(min_length=1, max_length=240)
    risk_class: RiskClass
    context: dict[str, Any] = Field(default_factory=dict)
    execute_action: bool = False

    @model_validator(mode="after")
    def planning_only(self) -> "EvaluationRequest":
        if self.execute_action:
            raise ValueError("policy evaluation never executes actions")
        return self


class EvaluationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    requester_id: str
    source_module: str
    action: str
    risk_class: RiskClass
    matched_policy_ids: list[UUID] = Field(default_factory=list)
    effect: PolicyEffect
    allowed: bool
    approval_required: bool
    required_approvals: int = 0
    reason: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalRequestCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    source_module: str = Field(min_length=1, max_length=160)
    action: str = Field(min_length=1, max_length=240)
    subject_id: str = Field(min_length=1, max_length=240)
    risk_class: RiskClass
    context: dict[str, Any] = Field(default_factory=dict)
    required_approvals: int = Field(default=1, ge=1, le=20)
    require_distinct_approvers: bool = True
    ttl_minutes: int = Field(default=60, ge=1, le=10080)
    execute_on_approval: bool = False
    human_approved: bool = True

    @model_validator(mode="after")
    def enforce_safety(self) -> "ApprovalRequestCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_on_approval:
            raise ValueError("approval does not execute the requested action")
        return self


class ApprovalRequestRecord(ApprovalRequestCreate):
    id: UUID = Field(default_factory=uuid4)
    state: RequestState = RequestState.PENDING
    approved_count: int = 0
    rejected_count: int = 0
    executed: bool = False
    expires_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=1))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalDecisionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    request_id: UUID
    approver_id: str = Field(min_length=1, max_length=120)
    decision: DecisionType
    reason: str = Field(default="", max_length=2000)
    human_approved: bool = True
    delegated: bool = False

    @model_validator(mode="after")
    def enforce_human(self) -> "ApprovalDecisionCreate":
        if not self.human_approved or self.delegated:
            raise ValueError("decisions require a direct human approver")
        return self


class ApprovalDecisionRecord(ApprovalDecisionCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExceptionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    policy_id: UUID
    subject_id: str = Field(min_length=1, max_length=240)
    reason: str = Field(min_length=1, max_length=3000)
    ttl_minutes: int = Field(default=30, ge=1, le=1440)
    human_approved: bool = True
    bypass_external_controls: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "ExceptionCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.bypass_external_controls:
            raise ValueError("external control bypasses are disabled")
        return self


class ExceptionRecord(ExceptionCreate):
    id: UUID = Field(default_factory=uuid4)
    state: ExceptionState = ExceptionState.REQUESTED
    granted_by: str | None = None
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExceptionDecision(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    grant: bool
    reason: str = Field(default="", max_length=2000)
    human_approved: bool = True


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    event_type: str
    resource_type: str
    resource_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PolicyApprovalStatus(BaseModel):
    version: str = "9.0"
    policies: int = 0
    pending_requests: int = 0
    open_exceptions: int = 0
    external_enforcement_enabled: bool = False
    approval_executes_actions: bool = False
    four_eyes_supported: bool = True
