from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class MarketBias(StrEnum):
    bullish = "bullish"
    bearish = "bearish"
    neutral = "neutral"


class SetupDecision(StrEnum):
    valid = "valid"
    watch = "watch"
    rejected = "rejected"


class TradeSide(StrEnum):
    buy = "buy"
    sell = "sell"


class MarketSnapshot(BaseModel):
    symbol: str = Field(min_length=1, max_length=30)
    timeframe: str = Field(min_length=1, max_length=10)
    price: float = Field(gt=0)
    higher_timeframe_bias: MarketBias = MarketBias.neutral
    liquidity_sweep: bool = False
    structure_shift: bool = False
    fair_value_gap: bool = False
    order_block: bool = False
    news_risk: bool = False
    spread_points: float = Field(default=0, ge=0)
    source_analysis_id: UUID | None = None


class RiskPolicy(BaseModel):
    account_balance: float = Field(gt=0)
    risk_percent: float = Field(default=1.0, gt=0, le=2.0)
    daily_drawdown_percent: float = Field(default=0, ge=0)
    max_daily_drawdown_percent: float = Field(default=4.0, gt=0, le=10)
    max_open_trades: int = Field(default=3, ge=0, le=20)
    current_open_trades: int = Field(default=0, ge=0, le=100)
    max_spread_points: float = Field(default=50, gt=0)


class SetupEvaluationRequest(BaseModel):
    snapshot: MarketSnapshot
    policy: RiskPolicy
    side: TradeSide
    entry: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_levels(self):
        if self.side == TradeSide.buy and not (self.stop_loss < self.entry < self.take_profit):
            raise ValueError("Buy levels must satisfy stop_loss < entry < take_profit")
        if self.side == TradeSide.sell and not (self.take_profit < self.entry < self.stop_loss):
            raise ValueError("Sell levels must satisfy take_profit < entry < stop_loss")
        return self


class TradingSetup(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol: str
    timeframe: str
    side: TradeSide
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    score: int = Field(ge=0, le=100)
    decision: SetupDecision
    reasons: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    suggested_risk_amount: float = Field(ge=0)
    human_approval_required: bool = True
    automatic_execution_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TradingAgentStatus(BaseModel):
    advisory_only: bool = True
    automatic_execution_enabled: bool = False
    human_approval_required: bool = True
    evaluated_setups: int
    valid_setups: int
