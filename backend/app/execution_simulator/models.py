from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderState(str, Enum):
    PENDING = "pending"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class BrokerExecutionProfile(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    spread_points: float = Field(default=20, ge=0)
    slippage_points: float = Field(default=5, ge=0)
    latency_ms: int = Field(default=80, ge=0, le=10_000)
    partial_fill_probability: float = Field(default=0.0, ge=0, le=1)
    commission_per_lot: float = Field(default=0.0, ge=0)


class SimulationOrderCreate(BaseModel):
    symbol: str = Field(min_length=3, max_length=40)
    side: OrderSide
    order_type: OrderType
    volume: float = Field(gt=0, le=100)
    requested_price: float = Field(gt=0)
    trigger_price: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    market_price: float = Field(gt=0)
    point_size: float = Field(default=0.01, gt=0)
    execution_profile: BrokerExecutionProfile
    automatic_execution: bool = False

    @model_validator(mode="after")
    def validate_safe_order(self):
        if self.automatic_execution:
            raise ValueError("Automatic execution is disabled; simulation only")
        if self.order_type != OrderType.MARKET and self.trigger_price is None:
            raise ValueError("Limit and stop orders require trigger_price")
        return self


class FillRecord(BaseModel):
    volume: float
    price: float
    slippage_points: float
    commission: float
    filled_at: datetime


class SimulationOrderRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol: str
    side: OrderSide
    order_type: OrderType
    requested_volume: float
    filled_volume: float = 0
    requested_price: float
    average_fill_price: float | None = None
    state: OrderState
    latency_ms: int
    fills: list[FillRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    human_approval_required: bool = True
    real_order_sent: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SimulatorStatus(BaseModel):
    version: str = "6.9"
    mode: str = "simulation_only"
    human_approval_required: bool = True
    automatic_execution_enabled: bool = False
    real_broker_orders_enabled: bool = False
    owner: str = "MASTER Brano"


class SimulationOrderList(BaseModel):
    items: list[SimulationOrderRecord]
    count: int


class ExecutionReport(BaseModel):
    total_orders: int
    filled_orders: int
    rejected_orders: int
    total_requested_volume: float
    total_filled_volume: float
    average_latency_ms: float
    average_slippage_points: float
    total_commission: float
