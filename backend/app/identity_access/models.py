from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class IdentityType(str, Enum):
    HUMAN = "human"
    AGENT = "agent"
    SERVICE = "service"


class IdentityState(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class AssignmentState(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class DelegationState(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    REJECTED = "rejected"


class IdentityCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    identity_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=240)
    identity_type: IdentityType
    attributes: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    capture_credentials: bool = False
    external_identity_sync: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "IdentityCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.capture_credentials:
            raise ValueError("credential capture is disabled")
        if self.external_identity_sync:
            raise ValueError("automatic external identity sync is disabled in v9.1")
        return self


class IdentityRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    identity_key: str
    display_name: str
    identity_type: IdentityType
    attributes: dict[str, Any]
    state: IdentityState = IdentityState.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Permission(BaseModel):
    resource: str = Field(min_length=1, max_length=200)
    actions: list[str] = Field(min_length=1, max_length=100)
    conditions: dict[str, Any] = Field(default_factory=dict)


class RoleCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    role_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=3000)
    permissions: list[Permission] = Field(default_factory=list, max_length=300)
    maximum_risk: str = Field(default="low", pattern=r"^(low|medium|high|critical)$")
    human_approved: bool = True
    wildcard_access: bool = False

    @model_validator(mode="after")
    def enforce_least_privilege(self) -> "RoleCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.wildcard_access:
            raise ValueError("wildcard access is disabled")
        for permission in self.permissions:
            if permission.resource == "*" or "*" in permission.actions:
                raise ValueError("wildcard permissions violate least privilege")
        return self


class RoleRecord(RoleCreate):
    id: UUID = Field(default_factory=uuid4)
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RoleAssignmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    identity_id: UUID
    role_id: UUID
    valid_minutes: int = Field(default=1440, ge=1, le=525600)
    reason: str = Field(default="", max_length=2000)
    human_approved: bool = True
    auto_renew: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "RoleAssignmentCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.auto_renew:
            raise ValueError("automatic role renewal is disabled")
        return self


class RoleAssignmentRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    identity_id: UUID
    role_id: UUID
    reason: str
    state: AssignmentState = AssignmentState.ACTIVE
    granted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    revoked_at: datetime | None = None


class DelegationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    delegator_identity_id: UUID
    delegate_identity_id: UUID
    role_id: UUID
    valid_minutes: int = Field(default=60, ge=1, le=10080)
    reason: str = Field(min_length=1, max_length=2000)
    requires_acceptance: bool = True
    human_approved: bool = True
    chain_delegation: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "DelegationCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.delegator_identity_id == self.delegate_identity_id:
            raise ValueError("self delegation is not allowed")
        if self.chain_delegation:
            raise ValueError("delegation chaining is disabled")
        return self


class DelegationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    delegator_identity_id: UUID
    delegate_identity_id: UUID
    role_id: UUID
    reason: str
    state: DelegationState
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    activated_at: datetime | None = None
    expires_at: datetime
    revoked_at: datetime | None = None


class AccessCheckRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    identity_id: UUID
    resource: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=120)
    context: dict[str, Any] = Field(default_factory=dict)
    execute_action: bool = False

    @model_validator(mode="after")
    def planning_only(self) -> "AccessCheckRequest":
        if self.execute_action:
            raise ValueError("access checks never execute actions")
        return self


class AccessDecision(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    identity_id: UUID
    resource: str
    action: str
    allowed: bool
    matched_role_ids: list[UUID] = Field(default_factory=list)
    reason: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IdentityMutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=2000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "IdentityMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    subject_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IdentityAccessStatus(BaseModel):
    version: str = "9.1"
    credential_capture_enabled: bool = False
    external_identity_sync_enabled: bool = False
    wildcard_permissions_enabled: bool = False
    delegation_chaining_enabled: bool = False
    access_checks_execute_actions: bool = False
    workspace_isolation: bool = True
    least_privilege_enforced: bool = True
