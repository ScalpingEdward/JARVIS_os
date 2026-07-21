from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ShadowPortfolioState(str, Enum):
    BLOCKED = "blocked"
    MARKET_PERMISSION_REQUIRED = "market-permission-required"
    INPUT_INVALID = "input-invalid"
    SAMPLE_INSUFFICIENT = "sample-insufficient"
    SIMULATION_PENDING = "simulation-pending"
    SIMULATION_READY = "simulation-ready"
    BREACH_DETECTED = "breach-detected"
    DEGRADATION_DETECTED = "degradation-detected"
    APPROVAL_REQUIRED = "approval-required"
    SHADOW_ACTIVE = "shadow-active"
    PROMOTION_CANDIDATE = "promotion-candidate"
    REJECTED = "rejected"
    MONITORING = "monitoring"
    FAILED = "failed"


class ShadowTradeInput(BaseModel):
    trade_id: str = Field(min_length=1, max_length=120)
    strategy_id: str = Field(min_length=1, max_length=120)
    symbol: str = Field(min_length=1, max_length=40)
    account_id: str = Field(min_length=1, max_length=120)
    side: str
    entry_price: float = Field(gt=0)
    exit_price: float = Field(gt=0)
    volume: float = Field(gt=0)
    pnl: float
    risk_amount: float = Field(gt=0)
    realized_rr: float
    slippage_bps: float = Field(default=0, ge=0)
    max_adverse_excursion_r: float = Field(default=0, ge=0)
    max_favorable_excursion_r: float = Field(default=0, ge=0)
    duration_seconds: int = Field(default=0, ge=0)
    routed_by_v19_06: bool = False
    market_allowed_by_v19_08: bool = False


class ShadowPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    upstream_risk_brain_blocked: bool = False
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    market_permission_approved: bool = False
    initial_equity: float = Field(gt=0)
    max_daily_loss_pct: float = Field(gt=0)
    max_total_drawdown_pct: float = Field(gt=0)
    min_sample_size: int = Field(default=20, ge=1)
    min_profit_factor: float = Field(default=1.2, ge=0)
    min_expectancy_r: float = Field(default=0.1)
    max_slippage_bps: float = Field(default=8, ge=0)
    promotion_min_trades: int = Field(default=30, ge=1)
    human_approved: bool = False
    trades: list[ShadowTradeInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_trade_ids(self):
        ids = [trade.trade_id for trade in self.trades]
        if len(ids) != len(set(ids)):
            raise ValueError("trade_id values must be unique")
        return self


class ShadowPortfolioExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = "activate-shadow"
    human_approved: bool | None = None


class ShadowStrategyResult(BaseModel):
    strategy_id: str
    trades: int
    wins: int
    losses: int
    win_rate_pct: float
    net_pnl: float
    expectancy_r: float
    profit_factor: float
    max_drawdown: float
    avg_slippage_bps: float
    risk_breaches: int
    recommendation: str


class ShadowPortfolioRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: ShadowPortfolioState
    detail: str
    request: ShadowPortfolioCreate
    ending_equity: float = 0
    net_pnl: float = 0
    win_rate_pct: float = 0
    expectancy_r: float = 0
    profit_factor: float = 0
    max_drawdown: float = 0
    max_drawdown_pct: float = 0
    max_daily_loss_pct_observed: float = 0
    avg_slippage_bps: float = 0
    risk_breaches: int = 0
    strategies: list[ShadowStrategyResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ShadowPortfolioStatus(BaseModel):
    module: str = "executive-shadow-portfolio-simulator"
    version: str = "19.09"
    workspace_id: str
    total_records: int
    active_records: int
    blocked_records: int


class ShadowPortfolioAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: ShadowPortfolioState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
