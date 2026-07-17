from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PolicyState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class Decision(str, Enum):
    ALLOW = "allow"
    RATE_LIMITED = "rate-limited"
    CIRCUIT_OPEN = "circuit-open"
    BULKHEAD_FULL = "bulkhead-full"
    RETRY_BUDGET_EXHAUSTED = "retry-budget-exhausted"


class Outcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    REJECTED = "rejected"


class PolicyCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    policy_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    target_service: str = Field(min_length=1, max_length=180)
    target_operation: str = Field(default="*", min_length=1, max_length=240)
    requests_per_window: int = Field(default=100, ge=1, le=1_000_000)
    window_seconds: int = Field(default=60, ge=1, le=86400)
    burst_capacity: int = Field(default=0, ge=0, le=1_000_000)
    failure_threshold: int = Field(default=5, ge=1, le=10_000)
    failure_window_seconds: int = Field(default=60, ge=1, le=86400)
    open_seconds: int = Field(default=30, ge=1, le=86400)
    half_open_max_calls: int = Field(default=1, ge=1, le=1000)
    bulkhead_max_concurrency: int = Field(default=10, ge=1, le=100_000)
    retry_budget: int = Field(default=20, ge=0, le=100_000)
    retry_window_seconds: int = Field(default=60, ge=1, le=86400)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_activation: bool = False
    execute_request: bool = False
    external_provider: bool = False

    @model_validator(mode="after")
    def safety(self) -> "PolicyCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_activation:
            raise ValueError("automatic resilience-policy activation is disabled")
        if self.execute_request:
            raise ValueError("resilience decisions never execute target requests")
        if self.external_provider:
            raise ValueError("external resilience providers are disabled")
        return self


class PolicyRecord(PolicyCreate):
    id: UUID = Field(default_factory=uuid4)
    state: PolicyState = PolicyState.DRAFT
    circuit_state: CircuitState = CircuitState.CLOSED
    circuit_opened_at: datetime | None = None
    active_calls: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Mutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=3000)
    human_approved: bool = True

    @model_validator(mode="after")
    def safety(self) -> "Mutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class AdmissionRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    policy_id: UUID
    subject_key: str = Field(min_length=1, max_length=240)
    correlation_id: str = Field(min_length=1, max_length=240)
    is_retry: bool = False
    evaluation_time: datetime | None = None
    human_approved: bool = True
    execute_request: bool = False

    @model_validator(mode="after")
    def safety(self) -> "AdmissionRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_request:
            raise ValueError("admission checks never execute target requests")
        return self


class AdmissionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    policy_id: UUID
    subject_key: str
    correlation_id: str
    decision: Decision
    retry_after_seconds: int = 0
    reason: str = ""
    reserved_slot: bool = False
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OutcomeRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    admission_id: UUID
    outcome: Outcome
    latency_ms: int = Field(default=0, ge=0, le=86_400_000)
    reason: str = Field(default="", max_length=3000)
    human_approved: bool = True

    @model_validator(mode="after")
    def safety(self) -> "OutcomeRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class OutcomeRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    policy_id: UUID
    admission_id: UUID
    outcome: Outcome
    latency_ms: int
    reason: str = ""
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsRecord(BaseModel):
    workspace_id: str
    policies: int
    active_policies: int
    open_circuits: int
    allowed: int
    rate_limited: int
    circuit_rejected: int
    bulkhead_rejected: int
    retry_rejected: int
    successes: int
    failures: int
    timeouts: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    entity_type: str
    entity_id: UUID | None = None
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResilienceStatus(BaseModel):
    version: str = "10.0"
    policies: int
    admissions: int
    outcomes: int
    open_circuits: int
    automatic_activation_enabled: bool = False
    executes_requests: bool = False
    external_provider_enabled: bool = False
