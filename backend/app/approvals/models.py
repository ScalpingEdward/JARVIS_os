from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ActorRole(StrEnum):
    viewer = "viewer"
    operator = "operator"
    approver = "approver"
    admin = "admin"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    consumed = "consumed"
    expired = "expired"


class ApprovalRequestCreate(BaseModel):
    action: str = Field(min_length=1, max_length=200)
    arguments: dict[str, Any] = Field(default_factory=dict)
    requested_by: str = Field(min_length=1, max_length=100)
    requester_role: ActorRole = ActorRole.operator
    risk: RiskLevel = RiskLevel.high
    reason: str = Field(min_length=1, max_length=1000)


class ApprovalRecord(ApprovalRequestCreate):
    id: UUID = Field(default_factory=uuid4)
    status: ApprovalStatus = ApprovalStatus.pending
    approved_by: str | None = None
    rejected_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None
    consumed_at: datetime | None = None


class ApprovalDecision(BaseModel):
    actor: str = Field(min_length=1, max_length=100)
    role: ActorRole
    note: str | None = Field(default=None, max_length=1000)


class ApprovalTokenResponse(BaseModel):
    approval: ApprovalRecord
    confirmation_token: str


class ApprovalConsume(BaseModel):
    confirmation_token: str = Field(min_length=20, max_length=500)
    actor: str = Field(min_length=1, max_length=100)


class AuditEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    event_type: str
    actor: str
    approval_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalListResponse(BaseModel):
    items: list[ApprovalRecord]
    count: int


class AuditListResponse(BaseModel):
    items: list[AuditEvent]
    count: int
