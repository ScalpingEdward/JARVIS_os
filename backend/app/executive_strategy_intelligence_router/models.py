from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class StrategyIntelligenceState(str, Enum):
    BLOCKED = "blocked"
    ALLOCATION_REQUIRED = "allocation-required"
    SIGNAL_INVALID = "signal-invalid"
    SIGNAL_STALE = "signal-stale"
    REGIME_MISMATCH = "regime-mismatch"
    DUPLICATE_SIGNAL = "duplicate-signal"
    COOLDOWN_ACTIVE = "cooldown-active"
    CONFLICT_DETECTED = "conflict-detected"
    CORRELATION_REJECTED = "correlation-rejected"
    RISK_REJECTED = "risk-rejected"
    APPROVAL_REQUIRED = "approval-required"
    ROUTE_READY = "route-ready"
    ROUTED = "routed"
    MONITORING = "monitoring"
    FAILED = "failed"


class StrategySignalInput(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=100)
    signal_id: str = Field(min_length=1, max_length=160)
    symbol: str = Field(min_length=1, max_length=30)
    side: str
    timeframe: str = Field(min_length=1, max_length=20)
    market_regime: str = Field(min_length=1, max_length=50)
    compatible_regimes: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=100)
    quality_score: float = Field(ge=0, le=100)
    expected_rr: float = Field(gt=0)
    proposed_risk: float = Field(gt=0)
    age_seconds: int = Field(ge=0)
    max_age_seconds: int = Field(default=300, gt=0)
    priority: int = Field(default=100, ge=0)
    cooldown_active: bool = False
    duplicate: bool = False
    correlation_score: float = Field(default=0, ge=0, le=1)
    multi_timeframe_confirmed: bool = False

    @model_validator(mode="after")
    def validate_side(self):
        if self.side.lower() not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        return self


class StrategyRoutingCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    allocation_approved: bool = False
    upstream_risk_brain_blocked: bool = False
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    available_risk_budget: float = Field(gt=0)
    minimum_confidence: float = Field(default=60, ge=0, le=100)
    minimum_quality: float = Field(default=60, ge=0, le=100)
    minimum_rr: float = Field(default=1.5, gt=0)
    maximum_correlation: float = Field(default=0.8, ge=0, le=1)
    human_approved: bool = False
    signals: list[StrategySignalInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_signal_ids(self):
        ids = [signal.signal_id for signal in self.signals]
        if len(ids) != len(set(ids)):
            raise ValueError("signal_id values must be unique")
        return self


class StrategyRoutingExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = "route"
    human_approved: bool | None = None


class StrategySignalResult(BaseModel):
    strategy_id: str
    signal_id: str
    score: float = 0
    selected: bool = False
    rejected: bool = False
    rejection_reason: str | None = None


class StrategyRoutingRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: StrategyIntelligenceState
    detail: str
    request: StrategyRoutingCreate
    selected_strategy_id: str | None = None
    selected_signal_id: str | None = None
    selected_symbol: str | None = None
    selected_side: str | None = None
    approved_risk: float = 0
    results: list[StrategySignalResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StrategyIntelligenceStatus(BaseModel):
    module: str = "executive-strategy-intelligence-router"
    version: str = "19.06"
    workspace_id: str
    total_records: int
    routed_records: int
    blocked_records: int


class StrategyIntelligenceAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: StrategyIntelligenceState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
