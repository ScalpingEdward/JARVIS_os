from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class EnvironmentProfile(StrEnum):
    local = "local"
    vps = "vps"
    staging = "staging"
    production = "production"


class ComponentKind(StrEnum):
    model_provider = "model_provider"
    mt5 = "mt5"
    tradingview = "tradingview"
    telegram = "telegram"
    research = "research"
    voice = "voice"
    email = "email"
    mobile_push = "mobile_push"


class ConfigState(StrEnum):
    draft = "draft"
    ready = "ready"
    degraded = "degraded"
    disabled = "disabled"


class SecretReference(BaseModel):
    name: str = Field(min_length=2, max_length=120, pattern=r"^[A-Z][A-Z0-9_]+$")
    source: str = Field(default="environment", max_length=60)
    required: bool = True


class ComponentConfigCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    kind: ComponentKind
    environment: EnvironmentProfile = EnvironmentProfile.local
    enabled: bool = True
    settings: dict[str, str | int | float | bool] = Field(default_factory=dict)
    secret_references: list[SecretReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_secret_values(self) -> "ComponentConfigCreate":
        forbidden = {"api_key", "token", "password", "secret", "private_key", "login_password"}
        for key, value in self.settings.items():
            normalized = key.lower()
            if any(part in normalized for part in forbidden) and str(value).strip():
                raise ValueError(f"Sensitive value '{key}' must use a secret reference")
        return self


class ComponentConfig(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    kind: ComponentKind
    environment: EnvironmentProfile
    enabled: bool
    settings: dict[str, str | int | float | bool]
    secret_references: list[SecretReference]
    state: ConfigState = ConfigState.draft
    missing_secrets: list[str] = Field(default_factory=list)
    validation_messages: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ComponentConfigList(BaseModel):
    items: list[ComponentConfig]
    count: int


class ReadinessCheck(BaseModel):
    component_id: UUID
    component_name: str
    ready: bool
    state: ConfigState
    missing_secrets: list[str]
    messages: list[str]


class ControlPlaneStatus(BaseModel):
    total_components: int
    ready_components: int
    degraded_components: int
    disabled_components: int
    missing_secret_references: int
    plaintext_secrets_stored: bool = False
    automatic_execution: bool = False
    automatic_order_execution: bool = False
    automatic_merge: bool = False
