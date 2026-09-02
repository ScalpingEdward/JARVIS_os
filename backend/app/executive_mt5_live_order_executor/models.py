from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class LiveOrderState(str, Enum):
    BLOCKED = "blocked"
    ADAPTER_REQUIRED = "adapter-required"
    ORDER_INVALID = "order-invalid"
    SYMBOL_UNAVAILABLE = "symbol-unavailable"
    QUOTE_STALE = "quote-stale"
    PRICE_DEVIATION_REJECTED = "price-deviation-rejected"
    VOLUME_REJECTED = "volume-rejected"
    STOPS_REJECTED = "stops-rejected"
    RISK_REJECTED = "risk-rejected"
    APPROVAL_REQUIRED = "approval-required"
    PREFLIGHT_READY = "preflight-ready"
    SUBMISSION_PENDING = "submission-pending"
    BROKER_REJECTED = "broker-rejected"
    PARTIAL_FILL = "partial-fill"
    EXECUTED = "executed"
    RECONCILIATION_REQUIRED = "reconciliation-required"
    CANCELLED = "cancelled"
    FAILED = "failed"


class LiveOrderCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    native_adapter_ready: bool = False
    account_login: int = Field(gt=0)
    approved_account_logins: list[int] = Field(default_factory=list)
    symbol: str = Field(min_length=1, max_length=32)
    side: str
    order_type: str = "market"
    volume: float = Field(gt=0)
    requested_price: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    quote_bid: float = Field(gt=0)
    quote_ask: float = Field(gt=0)
    quote_age_seconds: float = Field(ge=0)
    max_quote_age_seconds: float = Field(default=5, gt=0)
    max_deviation_points: int = Field(default=30, ge=0)
    symbol_point: float = Field(default=0.00001, gt=0)
    min_volume: float = Field(default=0.01, gt=0)
    max_volume: float = Field(default=100, gt=0)
    volume_step: float = Field(default=0.01, gt=0)
    min_stop_distance_points: int = Field(default=0, ge=0)
    expected_risk_amount: float = Field(default=0, ge=0)
    max_risk_amount: float = Field(default=0, ge=0)
    magic: int = Field(default=1901, ge=0)
    comment: str = Field(default="PHOENIX-v19.01", max_length=31)
    time_in_force: str = "gtc"
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    human_approved: bool = False
    risk_brain_blocked: bool = False

    @model_validator(mode="after")
    def validate_order(self):
        self.side = self.side.lower()
        self.order_type = self.order_type.lower()
        self.time_in_force = self.time_in_force.lower()
        if self.side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        if self.order_type not in {"market", "limit", "stop"}:
            raise ValueError("order_type must be market, limit or stop")
        if self.order_type != "market" and self.requested_price is None:
            raise ValueError("requested_price is required for pending orders")
        if self.time_in_force not in {"gtc", "day", "ioc", "fok"}:
            raise ValueError("unsupported time_in_force")
        return self


class LiveOrderExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = "submit"
    human_approved: bool | None = None


class LiveOrderRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: LiveOrderState
    detail: str
    request: LiveOrderCreate
    broker_order_id: int | None = None
    broker_deal_id: int | None = None
    broker_retcode: int | None = None
    broker_comment: str | None = None
    filled_volume: float = 0
    average_price: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LiveOrderStatus(BaseModel):
    module: str = "executive-mt5-live-order-executor"
    version: str = "19.01"
    workspace_id: str
    total_records: int
    executed_records: int
    blocked_records: int


class RemoteExecutionReport(BaseModel):
    """What a remote execution agent (real MetaTrader5 package, running on
    Windows next to the actual terminal -- AURON's own container can't load
    that package) reports back after it actually calls order_send() for a
    record AURON already marked PREFLIGHT_READY. AURON never re-derives or
    guesses any of this; it's the broker's own response, relayed as-is."""

    actor_id: str = Field(default="remote-execution-agent", min_length=1, max_length=100)
    broker_retcode: int | None = None
    broker_order_id: int | None = None
    broker_deal_id: int | None = None
    broker_comment: str | None = Field(default=None, max_length=500)
    filled_volume: float = Field(default=0, ge=0)
    average_price: float | None = Field(default=None, gt=0)


class LiveOrderAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: LiveOrderState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
