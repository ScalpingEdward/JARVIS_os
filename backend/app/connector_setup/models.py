from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from ..connectors.models import ConnectorKind, ConnectorPermission


class SetupState(str, Enum):
    draft = "draft"
    awaiting_user = "awaiting_user"
    authorizing = "authorizing"
    testing = "testing"
    ready = "ready"
    failed = "failed"


class AuthMethod(str, Enum):
    none = "none"
    environment_secret = "environment_secret"
    oauth2 = "oauth2"
    local_path = "local_path"
    bridge = "bridge"


class SetupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: ConnectorKind
    permissions: set[ConnectorPermission] = Field(default_factory=lambda: {ConnectorPermission.read})
    auth_method: AuthMethod
    secret_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("secret_refs")
    @classmethod
    def validate_secret_refs(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value.startswith("env:"):
                raise ValueError("Only env: secret references are allowed")
            if len(value) <= 4:
                raise ValueError("Secret reference name is required")
        return values


class PermissionConfirmation(BaseModel):
    permissions: set[ConnectorPermission]
    confirmed_by: str = Field(min_length=1, max_length=120)


class OAuthStartRequest(BaseModel):
    redirect_uri: str = Field(min_length=8, max_length=500)
    scopes: list[str] = Field(default_factory=list, max_length=50)


class OAuthStartResponse(BaseModel):
    authorization_url: str
    state: str
    expires_in_seconds: int = 600


class OAuthCallbackRequest(BaseModel):
    state: str = Field(min_length=16, max_length=256)
    code: str = Field(min_length=1, max_length=2048)


class ConnectionTestResult(BaseModel):
    ok: bool
    message: str
    latency_ms: int | None = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SetupRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    kind: ConnectorKind
    auth_method: AuthMethod
    permissions: set[ConnectorPermission]
    permissions_confirmed: bool = False
    secret_refs: list[str]
    metadata: dict[str, str]
    state: SetupState = SetupState.draft
    connector_id: UUID | None = None
    oauth_state: str | None = None
    oauth_expires_at: datetime | None = None
    last_test: ConnectionTestResult | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SetupListResponse(BaseModel):
    items: list[SetupRecord]
    count: int


class SetupPlatformStatus(BaseModel):
    total: int
    ready: int
    awaiting_user: int
    failed: int
    raw_secrets_stored: bool = False
    automatic_order_execution: bool = False
    automatic_merge: bool = False
