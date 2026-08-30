"""Shared models for trading strategies — market snapshots and trading setups."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class TradeSide(StrEnum):
    """Direction of a trade."""

    buy = "buy"
    sell = "sell"


class HTFBias(StrEnum):
    """Higher-timeframe bias (trend direction)."""

    bullish = "bullish"
    bearish = "bearish"
    neutral = "neutral"


class OrderBlockType(StrEnum):
    """Type of order block (ICT/SMC concept)."""

    bullish = "bullish"  # Last down candle before bullish move
    bearish = "bearish"  # Last up candle before bearish move


class FairValueGap(BaseModel):
    """Fair Value Gap (FVG) — imbalance between price candles."""

    side: Literal["bullish", "bearish"]
    top: float = Field(gt=0)
    bottom: float = Field(gt=0)
    formed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    mitigated: bool = False


class OrderBlock(BaseModel):
    """Order Block — last opposing candle before displacement."""

    type: OrderBlockType
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    open: float = Field(gt=0)
    close: float = Field(gt=0)
    formed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    mitigated: bool = False


class StructureLevel(BaseModel):
    """Swing high/low structure level."""

    level: float = Field(gt=0)
    type: Literal["high", "low"]
    strength: int = Field(ge=1, le=5, default=1)  # 1=weak, 5=strong
    formed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MarketSnapshot(BaseModel):
    """Complete market state snapshot for strategy decision-making.

    Combines current price, higher-timeframe bias, detected ICT/SMC structures
    (FVGs, order blocks, swing levels), and session info.
    """

    symbol: str = Field(min_length=1, max_length=32)
    current_price: float = Field(gt=0)
    bid: float = Field(gt=0)
    ask: float = Field(gt=0)
    spread: float = Field(ge=0)
    htf_bias: HTFBias = HTFBias.neutral
    session: Literal["asian", "london", "ny", "off"] = "off"
    fvgs: list[FairValueGap] = Field(default_factory=list)
    order_blocks: list[OrderBlock] = Field(default_factory=list)
    structure_levels: list[StructureLevel] = Field(default_factory=list)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TakeProfit(BaseModel):
    """Single take-profit level with partial-close percentage."""

    price: float = Field(gt=0)
    close_pct: float = Field(gt=0, le=100, description="% of position to close (e.g. 30, 50, 100)")
    label: str = Field(default="", max_length=50)


class TradingSetup(BaseModel):
    """A complete trading setup returned by a strategy.

    Includes entry, stop-loss, multiple take-profits, risk-reward, and confidence.
    """

    strategy_id: str = Field(min_length=1, max_length=50)
    strategy_name: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=32)
    side: TradeSide
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profits: list[TakeProfit] = Field(min_length=1, max_length=5)
    risk_reward: float = Field(gt=0, description="Overall RR ratio (e.g. 2.5 = 1:2.5)")
    confidence: float = Field(ge=0, le=100, description="Strategy confidence score (0-100)")
    reasoning: str = Field(default="", max_length=500, description="Why this setup was selected")
    invalidation_price: float | None = Field(
        default=None,
        gt=0,
        description="Price level where setup is invalidated (structure break)",
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StrategyResult(BaseModel):
    """Result of running a strategy against a market snapshot.

    Either contains a setup (if conditions met) or explains why no setup was generated.
    """

    strategy_id: str
    strategy_name: str
    symbol: str
    setup: TradingSetup | None = None
    no_setup_reason: str | None = Field(
        default=None,
        max_length=500,
        description="Reason why no setup was generated (if setup is None)",
    )
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
