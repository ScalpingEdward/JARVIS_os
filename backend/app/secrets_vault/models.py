from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class SecretState(str, Enum):
    ACTIVE = "active"
    ROTATION_DUE = "rotation_due"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class LeaseState(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    REJECTED = "rejected"


class RotationState(str, Enum):
    PLANNED = "planned"
    APPROVED = "approved"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SecretReferenceCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    secret_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    provider: str = Field(min_length=1, max_length=120)
    reference: str = Field(min_length=1, max_length=500)
    allowed_modules: list[str] = Field(default_factory=list, max_length=200)
    allowed_purposes: list[str] = Field(default_factory=list, max_length=200)
    rotation_interval_days: int = Field(default=90, ge=1, le=3650)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    plaintext_value: str | None = None
    export_secret: bool = False
    automatic_external_sync: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "SecretReferenceCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.plaintext_value:
            raise ValueError("plaintext secret values are never accepted")
        if self.export_secret:
            raise ValueError("secret export is disabled")
        if self.automatic_external_sync:
            raise ValueError("automatic external secret synchronization is disabled")
        if not self.reference.startswith(("env:", "vault:", "file-ref:", "os-keyring:")):
            raise ValueError("secret reference must use an approved reference scheme")
        return self


class SecretReferenceRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    secret_key: str
    provider: str
    reference: str
    allowed_modules: list[str]
    allowed_purposes: list[str]
    rotation_interval_days: int
    metadata: dict[str, Any]
    state: SecretState = SecretState.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_rotated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    next_rotation_at: datetime
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LeaseCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    secret_id: UUID
    source_module: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=1, max_length=240)
    ttl_minutes: int = Field(default=15, ge=1, le=1440)
    human_approved: bool = True
    reveal_value: bool = False
    auto_renew: bool = False
    execute_external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "LeaseCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.reveal_value:
            raise ValueError("secret values are never revealed by the lease engine")
        if self.auto_renew:
            raise ValueError("automatic lease renewal is disabled")
        if self.execute_external_action:
            raise ValueError("leases never execute external actions")
        return self


class LeaseRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    requester_id: str
    secret_id: UUID
    source_module: str
    purpose: str
    state: LeaseState = LeaseState.PENDING
    issued_reference: str | None = None
    approved_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    revoked_at: datetime | None = None


class LeaseDecision(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    approved: bool
    reason: str = Field(default="", max_length=2000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "LeaseDecision":
        if not self.human_approved:
            raise ValueError("direct human decision is required")
        return self


class RotationPlanCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    secret_id: UUID
    reason: str = Field(min_length=1, max_length=2000)
    scheduled_for: datetime
    human_approved: bool = True
    rotate_automatically: bool = False

    @model_validator(mode="after")
    def planning_only(self) -> "RotationPlanCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.rotate_automatically:
            raise ValueError("automatic secret rotation is disabled in v9.2")
        return self


class RotationPlanRecord(RotationPlanCreate):
    id: UUID = Field(default_factory=uuid4)
    state: RotationState = RotationState.PLANNED
    approved_by: str | None = None
    completed_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SecretMutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=2000)
    human_approved: bool = True


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    subject_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VaultStatus(BaseModel):
    version: str = "9.2"
    plaintext_storage_enabled: bool = False
    secret_export_enabled: bool = False
    automatic_rotation_enabled: bool = False
    automatic_lease_renewal_enabled: bool = False
    active_secrets: int = 0
    active_leases: int = 0
    rotation_plans: int = 0
