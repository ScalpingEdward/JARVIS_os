from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class MarketRegime(str, Enum):
    TREND = "trend"
    RANGE = "range"
    EXPANSION = "expansion"
    COMPRESSION = "compression"
    VOLATILITY_SPIKE = "volatility-spike"


class RiskEnvironment(str, Enum):
    RISK_ON = "risk-on"
    RISK_OFF = "risk-off"
    NEUTRAL = "neutral"


class TradePermission(str, Enum):
    TRADE_ALLOWED = "trade-allowed"
    BLOCKED = "blocked"


class MarketIntelligenceState(str, Enum):
    BLOCKED = "blocked"
    INPUT_INVALID = "input-invalid"
    DATA_STALE = "data-stale"
    NEWS_BLACKOUT = "news-blackout"
    ROLLOVER_BLOCKED = "rollover-blocked"
    LIQUIDITY_REJECTED = "liquidity-rejected"
    SPREAD_REJECTED = "spread-rejected"
    VOLATILITY_REJECTED = "volatility-rejected"
    REGIME_REJECTED = "regime-rejected"
    CORRELATION_REJECTED = "correlation-rejected"
    RISK_ENVIRONMENT_REJECTED = "risk-environment-rejected"
    APPROVAL_REQUIRED = "approval-required"
    MARKET_READY = "market-ready"
    TRADE_ALLOWED = "trade-allowed"
    MONITORING = "monitoring"
    FAILED = "failed"


class TimeframeRegimeInput(BaseModel):
    timeframe: str = Field(min_length=1, max_length=20)
    regime: MarketRegime
    trend_strength: float = Field(ge=0, le=100)
    volatility_percentile: float = Field(ge=0, le=100)


class MacroEventInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    impact: str = Field(pattern="^(low|medium|high)$")
    minutes_until_event: int
    affected_currencies: list[str] = Field(default_factory=list)


class MarketIntelligenceCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=30)
    asset_class: str = Field(pattern="^(forex|metals|indices|crypto)$")
    timestamp_age_seconds: int = Field(ge=0)
    max_data_age_seconds: int = Field(default=30, gt=0)
    session: str = Field(pattern="^(asian|london|new-york|overlap|lunch|closed)$")
    killzone_active: bool = False
    rollover_active: bool = False
    spread_bps: float = Field(ge=0)
    max_spread_bps: float = Field(gt=0)
    liquidity_score: float = Field(ge=0, le=100)
    minimum_liquidity_score: float = Field(default=40, ge=0, le=100)
    atr_percentile: float = Field(ge=0, le=100)
    realized_volatility_percentile: float = Field(ge=0, le=100)
    max_volatility_percentile: float = Field(default=95, gt=0, le=100)
    timeframes: list[TimeframeRegimeInput] = Field(min_length=1)
    required_regimes: list[MarketRegime] = Field(default_factory=list)
    macro_events: list[MacroEventInput] = Field(default_factory=list)
    news_blackout_before_minutes: int = Field(default=15, ge=0)
    news_blackout_after_minutes: int = Field(default=15, ge=0)
    risk_environment: RiskEnvironment = RiskEnvironment.NEUTRAL
    allowed_risk_environments: list[RiskEnvironment] = Field(default_factory=lambda: list(RiskEnvironment))
    usd_strength_score: float = Field(default=50, ge=0, le=100)
    gold_environment_score: float = Field(default=50, ge=0, le=100)
    crypto_environment_score: float = Field(default=50, ge=0, le=100)
    correlation_score: float = Field(default=0, ge=0, le=1)
    max_correlation_score: float = Field(default=0.85, ge=0, le=1)
    upstream_risk_brain_blocked: bool = False
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    human_approved: bool = False

    @model_validator(mode="after")
    def validate_timeframes(self):
        names = [item.timeframe for item in self.timeframes]
        if len(names) != len(set(names)):
            raise ValueError("timeframe values must be unique")
        return self


class MarketIntelligenceExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = "activate"
    human_approved: bool | None = None


class MarketIntelligenceRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: MarketIntelligenceState
    permission: TradePermission
    detail: str
    request: MarketIntelligenceCreate
    dominant_regime: MarketRegime | None = None
    regime_alignment_score: float = 0
    volatility_score: float = 0
    liquidity_environment_score: float = 0
    macro_environment_score: float = 0
    dynamic_market_score: float = 0
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MarketIntelligenceStatus(BaseModel):
    module: str = "executive-market-intelligence-regime"
    version: str = "19.08"
    workspace_id: str
    total_records: int
    allowed_records: int
    blocked_records: int


class MarketIntelligenceAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: MarketIntelligenceState
    permission: TradePermission
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
