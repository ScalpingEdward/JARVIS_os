from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ConfigurationState(str, Enum):
    blocked = "blocked"
    configuration_required = "configuration-required"
    schema_invalid = "schema-invalid"
    secret_reference_missing = "secret-reference-missing"
    configuration_drift = "configuration-drift"
    reload_required = "reload-required"
    configuration_valid = "configuration-valid"
    runtime_ready = "runtime-ready"


class ConfigurationScope(str, Enum):
    workspace = "workspace"
    environment = "environment"
    module = "module"
    broker = "broker"
    prop_firm = "prop-firm"
    strategy = "strategy"


class SecretReference(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    reference: str = Field(min_length=1, max_length=240)
    resolved: bool = False
    scope_verified: bool = False
    rotation_due: bool = False
    expired: bool = False


class ConfigurationObservation(BaseModel):
    policy_state: str = Field(default="ready-for-dispatch", min_length=1, max_length=40)
    schema_registered: bool = True
    schema_version_supported: bool = True
    inheritance_resolved: bool = True
    feature_flags_valid: bool = True
    runtime_overrides_valid: bool = True
    persisted: bool = True
    checksum_verified: bool = True
    runtime_checksum_verified: bool = True
    reload_acknowledged: bool = True
    rollback_checkpoint_available: bool = True
    raw_secrets_present: bool = False
    secret_references: list[SecretReference] = Field(default_factory=list)


class ConfigurationPolicy(BaseModel):
    require_policy_authorization: bool = True
    require_registered_schema: bool = True
    require_supported_schema_version: bool = True
    require_resolved_inheritance: bool = True
    require_valid_feature_flags: bool = True
    require_valid_overrides: bool = True
    require_persistence: bool = True
    require_checksum_verification: bool = True
    require_secret_resolution: bool = True
    require_secret_scope_verification: bool = True
    prohibit_raw_secrets: bool = True
    require_reload_ack: bool = True
    require_rollback_checkpoint: bool = True


class ConfigurationAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    configuration_id: UUID = Field(default_factory=uuid4)
    configuration_key: str = Field(min_length=1, max_length=180)
    version: int = Field(ge=1)
    schema_version: str = Field(min_length=1, max_length=60)
    scope: ConfigurationScope
    environment: str = Field(min_length=1, max_length=80)
    target_module: str = Field(min_length=1, max_length=180)
    values: dict[str, Any] = Field(default_factory=dict)
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    runtime_overrides: dict[str, Any] = Field(default_factory=dict)
    parent_configuration_ids: list[UUID] = Field(default_factory=list)
    observation: ConfigurationObservation = Field(default_factory=ConfigurationObservation)
    risk_brain_clear: bool = True
    policy: ConfigurationPolicy = Field(default_factory=ConfigurationPolicy)


class ConfigurationAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    configuration_id: UUID
    configuration_key: str
    version: int
    schema_version: str
    scope: ConfigurationScope
    environment: str
    target_module: str
    state: ConfigurationState
    runtime_ready: bool
    reload_required: bool
    rollback_available: bool
    recommended_action: str
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConfigurationStatusResponse(BaseModel):
    workspace_id: str
    configurations: int
    runtime_ready: int
    drifted_or_invalid: int
    latest_state: ConfigurationState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    configuration_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
