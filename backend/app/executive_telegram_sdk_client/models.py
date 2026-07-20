from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TelegramSdkClientState(str, Enum):
    blocked = "blocked"
    configuration_required = "configuration-required"
    dependency_unavailable = "dependency-unavailable"
    client_ready = "client-ready"
    dispatched = "dispatched"


class TelegramSdkRuntimeConfig(BaseModel):
    transport_type: str = Field(pattern="^(telethon|bot-api)$")
    sdk_package: str = Field(min_length=1, max_length=100)
    sdk_version: str = Field(min_length=1, max_length=60)
    session_reference: str | None = Field(default=None, max_length=250)
    api_id_reference: str | None = Field(default=None, max_length=250)
    api_hash_reference: str | None = Field(default=None, max_length=250)
    bot_token_reference: str | None = Field(default=None, max_length=250)
    proxy_reference: str | None = Field(default=None, max_length=250)
    references_resolved: bool = False
    raw_secret_values_present: bool = False
    session_file_embedded: bool = False
    read_only_mode: bool = True
    dependency_installed: bool = True
    import_verified: bool = True
    client_factory_verified: bool = True
    timeout_seconds: int = Field(default=20, gt=0, le=300)
    connection_retries: int = Field(default=3, ge=0, le=10)
    receive_updates: bool = True


class TelegramSdkClientPolicy(BaseModel):
    allowed_telethon_packages: list[str] = Field(default_factory=lambda: ["telethon"])
    allowed_bot_api_packages: list[str] = Field(default_factory=lambda: ["python-telegram-bot"])
    require_resolved_secret_references: bool = True
    prohibit_raw_secret_values: bool = True
    prohibit_embedded_session_file: bool = True
    require_read_only_mode: bool = True
    require_dependency_installed: bool = True
    require_import_verification: bool = True
    require_factory_verification: bool = True
    maximum_timeout_seconds: int = Field(default=60, gt=0)
    maximum_connection_retries: int = Field(default=5, ge=0)


class TelegramSdkClientAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    transport_assessment_id: str = Field(min_length=1, max_length=120)
    transport_state: str = Field(min_length=1, max_length=40)
    client_id: str = Field(min_length=1, max_length=100)
    config: TelegramSdkRuntimeConfig
    risk_brain_clear: bool = True
    policy: TelegramSdkClientPolicy = Field(default_factory=TelegramSdkClientPolicy)


class TelegramSdkClientScores(BaseModel):
    secret_isolation: int = Field(ge=0, le=100)
    dependency_readiness: int = Field(ge=0, le=100)
    factory_readiness: int = Field(ge=0, le=100)
    runtime_safety: int = Field(ge=0, le=100)
    configuration_quality: int = Field(ge=0, le=100)
    client_confidence: int = Field(ge=0, le=100)


class TelegramSdkClientAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    transport_assessment_id: str
    client_id: str
    transport_type: str
    sdk_package: str
    sdk_version: str
    state: TelegramSdkClientState
    dispatchable: bool
    target_module: str | None
    recommended_action: str
    scores: TelegramSdkClientScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelegramSdkClientStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: TelegramSdkClientState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
