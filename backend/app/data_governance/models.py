from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class DataClass(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class SubjectType(str, Enum):
    USER = "user"
    CUSTOMER = "customer"
    EMPLOYEE = "employee"
    AGENT = "agent"
    SYSTEM = "system"


class PolicyState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class HoldState(str, Enum):
    ACTIVE = "active"
    RELEASED = "released"


class RequestType(str, Enum):
    ACCESS = "access"
    EXPORT = "export"
    DELETE = "delete"
    RECTIFY = "rectify"
    RESTRICT = "restrict"


class RequestState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ActionType(str, Enum):
    RETAIN = "retain"
    ARCHIVE = "archive"
    ANONYMIZE = "anonymize"
    DELETE = "delete"


class ActionState(str, Enum):
    PLANNED = "planned"
    APPROVED = "approved"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ConsentState(str, Enum):
    GRANTED = "granted"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class RetentionPolicyCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    policy_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=240)
    target_modules: list[str] = Field(default_factory=list, max_length=300)
    data_classes: list[DataClass] = Field(default_factory=list, max_length=10)
    retention_days: int = Field(ge=1, le=36500)
    expiry_action: ActionType = ActionType.ARCHIVE
    legal_basis: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=4000)
    human_approved: bool = True
    automatic_delete: bool = False
    automatic_external_export: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "RetentionPolicyCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_delete:
            raise ValueError("automatic deletion is disabled in v9.4")
        if self.automatic_external_export:
            raise ValueError("automatic external export is disabled")
        return self


class RetentionPolicyRecord(RetentionPolicyCreate):
    id: UUID = Field(default_factory=uuid4)
    state: PolicyState = PolicyState.DRAFT
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DataAssetCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    asset_key: str = Field(min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9_.:-]+$")
    source_module: str = Field(min_length=1, max_length=160)
    data_class: DataClass
    subject_type: SubjectType = SubjectType.SYSTEM
    subject_reference: str | None = Field(default=None, max_length=240)
    purpose: str = Field(min_length=1, max_length=500)
    legal_basis: str = Field(min_length=1, max_length=500)
    policy_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    contains_secret: bool = False
    raw_content: str | None = None

    @model_validator(mode="after")
    def no_sensitive_payload(self) -> "DataAssetCreate":
        if self.contains_secret:
            raise ValueError("secret-bearing assets must be represented by references only")
        if self.raw_content is not None:
            raise ValueError("raw content storage is disabled; register metadata and references only")
        return self


class DataAssetRecord(DataAssetCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    archived: bool = False


class LegalHoldCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    hold_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    reason: str = Field(min_length=1, max_length=3000)
    asset_ids: list[UUID] = Field(default_factory=list, min_length=1, max_length=1000)
    expires_in_days: int | None = Field(default=None, ge=1, le=36500)
    human_approved: bool = True


class LegalHoldRecord(LegalHoldCreate):
    id: UUID = Field(default_factory=uuid4)
    state: HoldState = HoldState.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    released_at: datetime | None = None


class ConsentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    subject_reference: str = Field(min_length=1, max_length=240)
    purpose: str = Field(min_length=1, max_length=500)
    scopes: list[str] = Field(default_factory=list, min_length=1, max_length=100)
    valid_days: int | None = Field(default=None, ge=1, le=3650)
    evidence_reference: str = Field(min_length=1, max_length=500)
    human_confirmed: bool = True

    @model_validator(mode="after")
    def require_confirmation(self) -> "ConsentCreate":
        if not self.human_confirmed:
            raise ValueError("direct human consent confirmation is required")
        return self


class ConsentRecord(ConsentCreate):
    id: UUID = Field(default_factory=uuid4)
    state: ConsentState = ConsentState.GRANTED
    granted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    withdrawn_at: datetime | None = None


class PrivacyRequestCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    subject_reference: str = Field(min_length=1, max_length=240)
    request_type: RequestType
    reason: str = Field(default="", max_length=3000)
    target_modules: list[str] = Field(default_factory=list, max_length=300)
    human_verified: bool = True
    execute_external_action: bool = False

    @model_validator(mode="after")
    def planning_only(self) -> "PrivacyRequestCreate":
        if not self.human_verified:
            raise ValueError("subject verification is required")
        if self.execute_external_action:
            raise ValueError("privacy requests are planning-only in v9.4")
        return self


class PrivacyRequestRecord(PrivacyRequestCreate):
    id: UUID = Field(default_factory=uuid4)
    state: RequestState = RequestState.PENDING
    blockers: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GovernanceActionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    asset_id: UUID
    action_type: ActionType
    reason: str = Field(min_length=1, max_length=2000)
    human_approved: bool = True
    execute_now: bool = False

    @model_validator(mode="after")
    def planning_only(self) -> "GovernanceActionCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_now:
            raise ValueError("governance actions are recorded as plans only")
        return self


class GovernanceActionRecord(GovernanceActionCreate):
    id: UUID = Field(default_factory=uuid4)
    state: ActionState = ActionState.PLANNED
    blockers: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


class Mutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=2000)
    human_approved: bool = True


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    entity_type: str
    entity_id: UUID | None = None
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GovernanceStatus(BaseModel):
    version: str = "9.4"
    policies: int
    assets: int
    active_holds: int
    consents: int
    privacy_requests: int
    planned_actions: int
    automatic_deletion_enabled: bool = False
    automatic_export_enabled: bool = False
    executes_external_actions: bool = False
