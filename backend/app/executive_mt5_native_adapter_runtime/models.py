from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class NativeAdapterState(str, Enum):
    BLOCKED = "blocked"
    PIPELINE_REQUIRED = "pipeline-required"
    CONFIGURATION_INVALID = "configuration-invalid"
    PACKAGE_UNAVAILABLE = "package-unavailable"
    APPROVAL_REQUIRED = "approval-required"
    INITIALIZATION_PENDING = "initialization-pending"
    LOGIN_PENDING = "login-pending"
    ACCOUNT_MISMATCH = "account-mismatch"
    TERMINAL_UNHEALTHY = "terminal-unhealthy"
    SYMBOL_SYNC_REQUIRED = "symbol-sync-required"
    HEARTBEAT_STALE = "heartbeat-stale"
    RECONNECT_REQUIRED = "reconnect-required"
    ADAPTER_READY = "adapter-ready"
    DISCONNECTED = "disconnected"
    FAILED = "failed"


class NativeAdapterAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=100)
    pipeline_active: bool = False
    terminal_path_configured: bool = False
    credentials_reference_configured: bool = False
    requested_account_login: int = Field(gt=0)
    allowed_account_logins: list[int] = Field(default_factory=list)
    required_symbols: list[str] = Field(default_factory=list)
    max_heartbeat_age_seconds: int = Field(default=30, ge=1, le=300)
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    risk_brain_blocked: bool = False
    human_approved: bool = False


class NativeAdapterExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(connect|heartbeat|disconnect)$")
    human_approved: bool | None = None


class AdapterRuntimeEvidence(BaseModel):
    package_available: bool = False
    initialized: bool = False
    logged_in: bool = False
    terminal_connected: bool = False
    trade_allowed: bool = False
    account_login: int | None = None
    account_server: str | None = None
    visible_symbols: list[str] = Field(default_factory=list)
    last_error_code: int | None = None
    last_error_message: str | None = None
    heartbeat_at: datetime | None = None


class NativeAdapterAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    state: NativeAdapterState
    pipeline_active: bool
    terminal_path_configured: bool
    credentials_reference_configured: bool
    requested_account_login: int
    allowed_account_logins: list[int]
    required_symbols: list[str]
    max_heartbeat_age_seconds: int
    account_risk_approved: bool
    prop_rules_approved: bool
    risk_brain_blocked: bool
    human_approved: bool
    evidence: AdapterRuntimeEvidence = Field(default_factory=AdapterRuntimeEvidence)
    reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NativeAdapterStatusResponse(BaseModel):
    workspace_id: str
    module: str = "executive_mt5_native_adapter_runtime"
    version: str = "19.00"
    assessments: int
    ready: int


class NativeAdapterListResponse(BaseModel):
    items: list[NativeAdapterAssessment]
    count: int


class NativeAdapterAuditRecord(BaseModel):
    assessment_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: NativeAdapterState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
