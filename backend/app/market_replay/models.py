from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ReplayState(str, Enum):
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReplaySpeed(int, Enum):
    X1 = 1
    X5 = 5
    X10 = 10
    X50 = 50
    X100 = 100
    X500 = 500
    X1000 = 1000


class Candle(BaseModel):
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_ohlc(self) -> "Candle":
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be the maximum OHLC value")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be the minimum OHLC value")
        return self


class ReplaySessionCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    timeframe: str = Field(min_length=1, max_length=10)
    candles: list[Candle] = Field(min_length=2)
    speed: ReplaySpeed = ReplaySpeed.X1
    initial_balance: float = Field(default=10000, gt=0)
    human_approval_required: bool = True
    automatic_execution: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "ReplaySessionCreate":
        if self.automatic_execution:
            raise ValueError("automatic execution is disabled")
        if not self.human_approval_required:
            raise ValueError("human approval is required")
        if any(a.timestamp >= b.timestamp for a, b in zip(self.candles, self.candles[1:])):
            raise ValueError("candles must be strictly chronological")
        return self


class ReplaySession(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol: str
    timeframe: str
    candles: list[Candle]
    speed: ReplaySpeed
    initial_balance: float
    balance: float
    equity: float
    cursor: int = 0
    state: ReplayState = ReplayState.READY
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    human_approval_required: bool = True
    automatic_execution: bool = False


class ReplayStepRequest(BaseModel):
    bars: int = Field(default=1, ge=1, le=1000)


class ReplayReport(BaseModel):
    session_id: UUID
    symbol: str
    timeframe: str
    processed_bars: int
    total_bars: int
    progress_pct: float
    current_price: float | None
    balance: float
    equity: float
    state: ReplayState
    recommendation: str


class ReplayStatus(BaseModel):
    service: str = "market-replay"
    version: str = "7.0"
    simulation_only: bool = True
    live_broker_connection: bool = False
    automatic_execution: bool = False
    human_approval_required: bool = True
