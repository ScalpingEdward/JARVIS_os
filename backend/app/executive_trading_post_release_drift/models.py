from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class MonitoringState(str, Enum):
    stable = "stable"
    watch = "watch"
    reduce = "reduce"
    shadow = "shadow"
    blocked = "blocked"


class DriftSeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class DriftDimension(str, Enum):
    performance = "performance"
    risk = "risk"
    execution = "execution"
    infrastructure = "infrastructure"
    data = "data"
    model = "model"


class BaselineMetric(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    baseline_value: float
    current_value: float
    tolerance_percent: float = Field(default=10, ge=0, le=100)
    higher_is_better: bool = True
    dimension: DriftDimension


class MonitoringInput(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    symbol: str = Field(min_length=1, max_length=30)
    account_profile: str = Field(min_length=1, max_length=100)
    release_state: str = Field(default="reduced_live", max_length=30)
    approved_risk_multiplier: float = Field(default=0.5, ge=0, le=1)
    observation_trades: int = Field(default=0, ge=0)
    minimum_observation_trades: int = Field(default=10, ge=1, le=10000)
    stable_minutes: int = Field(default=0, ge=0)
    minimum_stable_minutes: int = Field(default=60, ge=1, le=100000)
    incident_recurrence_count: int = Field(default=0, ge=0)
    open_critical_issues: int = Field(default=0, ge=0)
    risk_state: str = Field(default="normal", max_length=30)
    readiness_state: str = Field(default="ready", max_length=30)
    metrics: list[BaselineMetric] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_metrics(self):
        names = [item.name for item in self.metrics]
        if len(names) != len(set(names)):
            raise ValueError("Baseline metric names must be unique")
        return self


class DriftSignal(BaseModel):
    metric_name: str
    dimension: DriftDimension
    severity: DriftSeverity
    deviation_percent: float
    message: str
    blocking: bool
    remediation: str


class MonitoringScores(BaseModel):
    baseline_fidelity: float = Field(ge=0, le=100)
    performance_stability: float = Field(ge=0, le=100)
    risk_stability: float = Field(ge=0, le=100)
    execution_stability: float = Field(ge=0, le=100)
    operational_stability: float = Field(ge=0, le=100)
    promotion_readiness: float = Field(ge=0, le=100)
    overall_health: float = Field(ge=0, le=100)


class MonitoringAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    source_key: str
    symbol: str
    account_profile: str
    state: MonitoringState
    recommended_risk_multiplier: float = Field(ge=0, le=1)
    scores: MonitoringScores
    drift_signals: list[DriftSignal]
    reasons: list[str]
    promotion_allowed: bool = False
    regression_required: bool = False
    autonomous_actions_enabled: bool = False
    assessed_at: datetime


class MonitoringStatusResponse(BaseModel):
    version: str = "18.40"
    assessments: int
    stable: int
    watching: int
    reduced: int
    shadow: int
    blocked: int
    critical_drifts: int
    autonomous_actions_enabled: bool = False


class MonitoringListResponse(BaseModel):
    items: list[MonitoringAssessment]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    assessment_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
