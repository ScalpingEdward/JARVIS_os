from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class SLOState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class IndicatorKind(str, Enum):
    AVAILABILITY = "availability"
    SUCCESS_RATE = "success-rate"
    LATENCY = "latency"
    FRESHNESS = "freshness"
    CUSTOM_RATIO = "custom-ratio"


class SLOHealth(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    AT_RISK = "at-risk"
    EXHAUSTED = "exhausted"


class BudgetAction(str, Enum):
    NONE = "none"
    REVIEW = "review"
    FREEZE_PLANNED = "freeze-planned"
    ESCALATION_PLANNED = "escalation-planned"


class SLOCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    slo_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=240)
    service_key: str = Field(min_length=1, max_length=180)
    operation: str = Field(default="*", min_length=1, max_length=240)
    indicator_kind: IndicatorKind
    objective_percent: float = Field(ge=0.0, le=100.0)
    window_seconds: int = Field(default=2_592_000, ge=60, le=31_536_000)
    latency_threshold_ms: int | None = Field(default=None, ge=1, le=86_400_000)
    warning_budget_remaining_percent: float = Field(default=25.0, ge=0.0, le=100.0)
    critical_budget_remaining_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    fast_burn_threshold: float = Field(default=14.4, ge=0.0, le=10000.0)
    slow_burn_threshold: float = Field(default=2.0, ge=0.0, le=10000.0)
    labels: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_activation: bool = False
    automatic_enforcement: bool = False
    external_provider: bool = False

    @model_validator(mode="after")
    def validate_slo(self) -> "SLOCreate":
        if self.indicator_kind == IndicatorKind.LATENCY and self.latency_threshold_ms is None:
            raise ValueError("latency objectives require latency_threshold_ms")
        if self.critical_budget_remaining_percent > self.warning_budget_remaining_percent:
            raise ValueError("critical budget threshold cannot exceed warning threshold")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_activation:
            raise ValueError("automatic SLO activation is disabled")
        if self.automatic_enforcement:
            raise ValueError("SLO evaluations never enforce operational changes")
        if self.external_provider:
            raise ValueError("external SLO providers are disabled")
        return self


class SLORecord(SLOCreate):
    id: UUID = Field(default_factory=uuid4)
    state: SLOState = SLOState.DRAFT
    health: SLOHealth = SLOHealth.UNKNOWN
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Mutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=3000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "Mutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class MeasurementCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    slo_id: UUID
    total_events: int = Field(ge=0, le=10_000_000_000)
    good_events: int = Field(ge=0, le=10_000_000_000)
    window_start: datetime
    window_end: datetime
    source_reference: str = Field(default="", max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    collect_external: bool = False
    enforce_action: bool = False

    @model_validator(mode="after")
    def validate_measurement(self) -> "MeasurementCreate":
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")
        if self.good_events > self.total_events:
            raise ValueError("good_events cannot exceed total_events")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.collect_external:
            raise ValueError("automatic external metric collection is disabled")
        if self.enforce_action:
            raise ValueError("measurements never execute operational actions")
        return self


class MeasurementRecord(MeasurementCreate):
    id: UUID = Field(default_factory=uuid4)
    observed_percent: float
    error_percent: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvaluationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    slo_id: UUID
    measurement_id: UUID
    objective_percent: float
    observed_percent: float
    allowed_bad_events: float
    consumed_bad_events: float
    budget_remaining_percent: float
    burn_rate: float
    health: SLOHealth
    recommended_action: BudgetAction = BudgetAction.NONE
    requires_review: bool = False
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsRecord(BaseModel):
    workspace_id: str
    slos: int
    active_slos: int
    healthy_slos: int
    at_risk_slos: int
    exhausted_slos: int
    measurements: int
    evaluations: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    entity_type: str
    entity_id: UUID | None = None
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SLOStatus(BaseModel):
    version: str = "10.1"
    slos: int
    measurements: int
    evaluations: int
    exhausted_slos: int
    automatic_activation_enabled: bool = False
    automatic_enforcement_enabled: bool = False
    external_provider_enabled: bool = False
