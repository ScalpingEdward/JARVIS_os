from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ReadinessState(str, Enum):
    ready = "ready"
    conditional = "conditional"
    wait = "wait"
    blocked = "blocked"


class BugSeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class ComponentState(str, Enum):
    healthy = "healthy"
    degraded = "degraded"
    unavailable = "unavailable"


class BugSignal(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    component: str = Field(min_length=1, max_length=100)
    severity: BugSeverity
    message: str = Field(min_length=1, max_length=500)
    blocking: bool = False


class ReadinessInput(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    symbol: str = Field(min_length=1, max_length=30)
    account_profile: str = Field(min_length=1, max_length=100)
    market_regime_allowed: bool = True
    evidence_score: float = Field(default=70, ge=0, le=100)
    strategy_score: float = Field(default=70, ge=0, le=100)
    portfolio_health: str = Field(default="acceptable", max_length=30)
    risk_state: str = Field(default="normal", max_length=30)
    trading_decision: str = Field(default="approve", max_length=30)
    session_open: bool = True
    killzone_active: bool = True
    spread_score: float = Field(default=80, ge=0, le=100)
    volatility_score: float = Field(default=70, ge=0, le=100)
    news_risk: float = Field(default=0, ge=0, le=100)
    broker_state: ComponentState = ComponentState.healthy
    feed_state: ComponentState = ComponentState.healthy
    vps_state: ComponentState = ComponentState.healthy
    symbol_available: bool = True
    data_age_seconds: int = Field(default=0, ge=0)
    max_data_age_seconds: int = Field(default=30, ge=1, le=3600)
    latency_ms: float = Field(default=50, ge=0)
    max_latency_ms: float = Field(default=500, gt=0)
    clock_drift_ms: float = Field(default=0, ge=0)
    max_clock_drift_ms: float = Field(default=1000, gt=0)
    open_bug_signals: list[BugSignal] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source(self):
        codes = [item.code for item in self.open_bug_signals]
        if len(codes) != len(set(codes)):
            raise ValueError("Bug signal codes must be unique")
        return self


class ReadinessScores(BaseModel):
    market_readiness: float = Field(ge=0, le=100)
    decision_readiness: float = Field(ge=0, le=100)
    execution_readiness: float = Field(ge=0, le=100)
    infrastructure_health: float = Field(ge=0, le=100)
    data_quality: float = Field(ge=0, le=100)
    bug_health: float = Field(ge=0, le=100)
    overall_readiness: float = Field(ge=0, le=100)


class DetectedIssue(BaseModel):
    code: str
    component: str
    severity: BugSeverity
    message: str
    blocking: bool
    remediation: str


class ReadinessAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    source_key: str
    symbol: str
    account_profile: str
    state: ReadinessState
    scores: ReadinessScores
    detected_issues: list[DetectedIssue]
    reasons: list[str]
    trade_allowed: bool = False
    autonomous_execution_enabled: bool = False
    assessed_at: datetime


class ReadinessStatusResponse(BaseModel):
    version: str = "18.37"
    assessments: int
    ready: int
    conditional: int
    waiting: int
    blocked: int
    open_critical_issues: int
    autonomous_execution_enabled: bool = False


class ReadinessListResponse(BaseModel):
    items: list[ReadinessAssessment]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    assessment_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
