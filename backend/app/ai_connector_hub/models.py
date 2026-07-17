from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ProviderType(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROK = "grok"
    DEEPSEEK = "deepseek"
    MISTRAL = "mistral"
    OLLAMA = "ollama"
    GENERIC = "generic"


class ProviderState(str, Enum):
    REGISTERED = "registered"
    ACTIVE = "active"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    QUARANTINED = "quarantined"


class RequestState(str, Enum):
    PLANNED = "planned"
    ROUTED = "routed"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class RoutingStrategy(str, Enum):
    BALANCED = "balanced"
    LOWEST_COST = "lowest_cost"
    LOWEST_LATENCY = "lowest_latency"
    HIGHEST_QUALITY = "highest_quality"
    LOCAL_FIRST = "local_first"


class ModelProfile(BaseModel):
    model_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_.:/-]+$")
    capabilities: list[str] = Field(min_length=1, max_length=100)
    input_cost_per_million: float = Field(default=0.0, ge=0, le=100000)
    output_cost_per_million: float = Field(default=0.0, ge=0, le=100000)
    quality_score: float = Field(default=0.5, ge=0, le=1)
    latency_score: float = Field(default=0.5, ge=0, le=1)
    context_window: int = Field(default=8192, ge=1, le=10000000)
    enabled: bool = True


class ProviderRegister(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    provider_key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9_.-]+$")
    provider_type: ProviderType
    display_name: str = Field(min_length=1, max_length=200)
    models: list[ModelProfile] = Field(min_length=1, max_length=200)
    monthly_budget: float = Field(default=0.0, ge=0, le=1000000)
    local_provider: bool = False
    supports_dry_run: bool = True
    human_approved: bool = True
    automatic_paid_requests: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "ProviderRegister":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_paid_requests:
            raise ValueError("automatic paid AI requests are disabled")
        return self


class ProviderRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    provider_key: str
    provider_type: ProviderType
    display_name: str
    models: list[ModelProfile]
    monthly_budget: float
    current_month_spend: float = 0.0
    local_provider: bool
    supports_dry_run: bool
    state: ProviderState = ProviderState.REGISTERED
    health_message: str = "Not activated"
    request_count: int = 0
    failure_count: int = 0
    last_heartbeat_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProviderMutation(BaseModel):
    human_approved: bool = True
    reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def require_approval(self) -> "ProviderMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class RoutingRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    capability: str = Field(min_length=1, max_length=160)
    estimated_input_tokens: int = Field(default=0, ge=0, le=10000000)
    estimated_output_tokens: int = Field(default=0, ge=0, le=10000000)
    strategy: RoutingStrategy = RoutingStrategy.BALANCED
    preferred_provider_keys: list[str] = Field(default_factory=list, max_length=20)
    excluded_provider_keys: list[str] = Field(default_factory=list, max_length=20)
    maximum_estimated_cost: float = Field(default=1.0, ge=0, le=100000)
    require_local: bool = False
    dry_run: bool = True
    human_approved: bool = True
    execute_provider_request: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "RoutingRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if not self.dry_run:
            raise ValueError("v8.1 only permits dry-run routing")
        if self.execute_provider_request:
            raise ValueError("real provider execution is disabled")
        return self


class RoutingCandidate(BaseModel):
    provider_id: UUID
    provider_key: str
    model_key: str
    estimated_cost: float
    score: float
    reasons: list[str] = Field(default_factory=list)


class RoutingDecision(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    requester_id: str
    capability: str
    strategy: RoutingStrategy
    state: RequestState
    selected: RoutingCandidate | None = None
    candidates: list[RoutingCandidate] = Field(default_factory=list)
    blocked_reason: str | None = None
    dry_run: bool = True
    provider_request_executed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UsageRecordCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    provider_id: UUID
    model_key: str = Field(min_length=1, max_length=160)
    input_tokens: int = Field(default=0, ge=0, le=10000000)
    output_tokens: int = Field(default=0, ge=0, le=10000000)
    actual_cost: float = Field(default=0.0, ge=0, le=100000)
    success: bool = True
    dry_run: bool = True
    human_approved: bool = True

    @model_validator(mode="after")
    def enforce_usage_safety(self) -> "UsageRecordCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if not self.dry_run and self.actual_cost > 0:
            raise ValueError("paid usage recording requires a future execution release")
        return self


class UsageRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    provider_id: UUID
    model_key: str
    input_tokens: int
    output_tokens: int
    actual_cost: float
    success: bool
    dry_run: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AIConnectorHubStatus(BaseModel):
    service: str = "ai-connector-hub"
    version: str = "8.1"
    registered_providers: int
    active_providers: int
    degraded_providers: int
    available_models: int
    routing_decisions: int
    usage_records: int
    estimated_total_spend: float
    dry_run_only: bool = True
    real_provider_execution: bool = False
    automatic_paid_requests: bool = False
    budget_enforcement_enabled: bool = True
    fallback_routing_enabled: bool = True
