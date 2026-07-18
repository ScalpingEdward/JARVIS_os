from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class Environment(str, Enum):
    DEV = "dev"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class FlagState(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class ConfigState(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ACTIVE = "active"
    RETIRED = "retired"


class Mutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=4000)
    human_approved: bool = True

    @model_validator(mode="after")
    def validate_human(self) -> "Mutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class FeatureFlagCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    flag_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=6000)
    environment: Environment
    enabled_value: Any = True
    disabled_value: Any = False
    rollout_percentage: int = Field(default=0, ge=0, le=100)
    target_user_ids: list[str] = Field(default_factory=list, max_length=10000)
    dependency_flag_keys: list[str] = Field(default_factory=list, max_length=200)
    expires_at: datetime | None = None
    required_approvals: int = Field(default=1, ge=1, le=20)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_activation: bool = False
    automatic_rollout: bool = False
    external_provider: bool = False

    @model_validator(mode="after")
    def safety(self) -> "FeatureFlagCreate":
        if self.flag_key in self.dependency_flag_keys:
            raise ValueError("feature flag cannot depend on itself")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_activation:
            raise ValueError("automatic feature-flag activation is disabled")
        if self.automatic_rollout:
            raise ValueError("automatic rollout is disabled")
        if self.external_provider:
            raise ValueError("external feature-flag providers are disabled")
        return self


class FeatureFlagRecord(FeatureFlagCreate):
    id: UUID = Field(default_factory=uuid4)
    state: FlagState = FlagState.DRAFT
    approval_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    flag_id: UUID
    comment: str = Field(default="", max_length=4000)
    human_approved: bool = True
    automatic_decision: bool = False

    @model_validator(mode="after")
    def safety(self) -> "ApprovalCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_decision:
            raise ValueError("automatic approval decisions are disabled")
        return self


class ApprovalRecord(ApprovalCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConfigEntryCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    namespace: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    environment: Environment
    value: Any
    schema_reference: str = Field(default="", max_length=1000)
    required_approvals: int = Field(default=1, ge=1, le=20)
    secret_reference: str | None = Field(default=None, max_length=1000)
    human_approved: bool = True
    apply_change: bool = False
    external_provider: bool = False

    @model_validator(mode="after")
    def safety(self) -> "ConfigEntryCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.apply_change:
            raise ValueError("configuration records never apply runtime changes")
        if self.external_provider:
            raise ValueError("external configuration providers are disabled")
        return self


class ConfigEntryRecord(ConfigEntryCreate):
    id: UUID = Field(default_factory=uuid4)
    version: int = 1
    state: ConfigState = ConfigState.DRAFT
    approval_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConfigApprovalCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    config_id: UUID
    comment: str = Field(default="", max_length=4000)
    human_approved: bool = True
    automatic_decision: bool = False

    @model_validator(mode="after")
    def safety(self) -> "ConfigApprovalCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_decision:
            raise ValueError("automatic approval decisions are disabled")
        return self


class ConfigApprovalRecord(ConfigApprovalCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvaluationRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    flag_key: str = Field(min_length=1, max_length=180)
    environment: Environment
    subject_id: str = Field(min_length=1, max_length=240)


class EvaluationResult(BaseModel):
    flag_key: str
    enabled: bool
    value: Any
    reason: str


class MetricsRecord(BaseModel):
    workspace_id: str
    flags: int
    active_flags: int
    pending_review: int
    configs: int
    active_configs: int


class ConfigFeatureStatus(BaseModel):
    version: str = "10.7"
    automatic_activation: bool = False
    automatic_rollout: bool = False
    runtime_apply: bool = False
    external_providers: bool = False
    human_approval_required: bool = True
