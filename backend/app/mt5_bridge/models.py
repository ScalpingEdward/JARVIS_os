from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MT5ConnectionState(StrEnum):
    connected = "connected"
    stale = "stale"
    disconnected = "disconnected"


class MT5TerminalRegister(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    terminal_path: str = Field(min_length=1, max_length=500)
    account_login: int = Field(gt=0)
    broker: str = Field(min_length=1, max_length=150)
    server: str = Field(min_length=1, max_length=150)
    read_only: bool = True


class MT5TerminalRecord(MT5TerminalRegister):
    id: UUID = Field(default_factory=uuid4)
    state: MT5ConnectionState = MT5ConnectionState.disconnected
    bridge_version: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    last_heartbeat_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MT5Heartbeat(BaseModel):
    bridge_version: str = Field(min_length=1, max_length=50)
    latency_ms: int = Field(ge=0, le=60000)


class MT5AccountSnapshot(BaseModel):
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float | None = None
    floating_pnl: float = 0
    daily_pnl: float = 0
    currency: str = Field(default="USD", min_length=3, max_length=10)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MT5Position(BaseModel):
    ticket: int
    symbol: str
    side: str
    volume: float = Field(gt=0)
    open_price: float
    current_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    profit: float = 0
    opened_at: datetime


class MT5PendingOrder(BaseModel):
    ticket: int
    symbol: str
    order_type: str
    volume: float = Field(gt=0)
    price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    expires_at: datetime | None = None


class MT5Deal(BaseModel):
    ticket: int
    order_ticket: int | None = None
    symbol: str
    side: str
    volume: float
    price: float
    profit: float = 0
    commission: float = 0
    swap: float = 0
    executed_at: datetime


class MT5Tick(BaseModel):
    symbol: str
    bid: float
    ask: float
    last: float | None = None
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MT5Candle(BaseModel):
    symbol: str
    timeframe: str
    opened_at: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int = Field(ge=0)


class MT5JournalEntry(BaseModel):
    level: str = Field(default="info", max_length=20)
    message: str = Field(min_length=1, max_length=2000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MT5SnapshotIngest(BaseModel):
    account: MT5AccountSnapshot
    positions: list[MT5Position] = Field(default_factory=list)
    pending_orders: list[MT5PendingOrder] = Field(default_factory=list)
    deals: list[MT5Deal] = Field(default_factory=list)
    ticks: list[MT5Tick] = Field(default_factory=list)
    candles: list[MT5Candle] = Field(default_factory=list)
    journal: list[MT5JournalEntry] = Field(default_factory=list)


class MT5TerminalData(BaseModel):
    terminal: MT5TerminalRecord
    account: MT5AccountSnapshot | None = None
    positions: list[MT5Position] = Field(default_factory=list)
    pending_orders: list[MT5PendingOrder] = Field(default_factory=list)
    deals: list[MT5Deal] = Field(default_factory=list)
    ticks: list[MT5Tick] = Field(default_factory=list)
    candles: list[MT5Candle] = Field(default_factory=list)
    journal: list[MT5JournalEntry] = Field(default_factory=list)


class MT5BridgeStatus(BaseModel):
    terminals: int
    connected: int
    stale: int
    disconnected: int
    read_only_enforced: bool = True
    order_execution_enabled: bool = False
