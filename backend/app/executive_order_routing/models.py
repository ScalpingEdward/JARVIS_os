from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class OrderRoutingState(str, Enum):
    blocked = "blocked"
    approval_required = "approval-required"
    market_data_required = "market-data-required"
    broker_session_required = "broker-session-required"
    risk_rejected = "risk-rejected"
    invalid_order = "invalid-order"
    route_unavailable = "route-unavailable"
    pretrade_approved = "pretrade-approved"
    ready_for_dispatch = "ready-for-dispatch"


class OrderSide(str, Enum):
    buy = "buy"
    sell = "sell"


class OrderType(str, Enum):
    market = "market"
    limit = "limit"
    stop = "stop"
    stop_limit = "stop-limit"


class TimeInForce(str, Enum):
    gtc = "gtc"
    ioc = "ioc"
    fok = "fok"
    day = "day"


class OrderRoutingObservation(BaseModel):
    policy_state: str = Field(default="ready-for-dispatch", min_length=1, max_length=40)
    market_data_state: str = Field(default="stream-ready", min_length=1, max_length=40)
    broker_session_state: str = Field(default="session-ready", min_length=1, max_length=40)
    symbol_registered: bool = True
    market_open: bool = True
    route_available: bool = True
    account_trade_enabled: bool = True
    margin_sufficient: bool = True
    exposure_within_limits: bool = True
    daily_loss_within_limits: bool = True
    max_drawdown_within_limits: bool = True
    spread_within_limit: bool = True
    slippage_within_limit: bool = True
    stop_loss_valid: bool = True
    take_profit_valid: bool = True
    volume_valid: bool = True
    price_valid: bool = True
    duplicate_intent: bool = False
    human_approval_present: bool = False


class OrderRoutingPolicy(BaseModel):
    require_policy_authorization: bool = True
    require_market_data: bool = True
    require_broker_session: bool = True
    require_registered_symbol: bool = True
    require_market_open: bool = True
    require_trade_enabled: bool = True
    require_margin: bool = True
    enforce_exposure_limits: bool = True
    enforce_daily_loss_limit: bool = True
    enforce_max_drawdown: bool = True
    enforce_spread_limit: bool = True
    enforce_slippage_limit: bool = True
    require_stop_loss: bool = True
    require_take_profit: bool = False
    require_human_approval: bool = True


class OrderIntentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    intent_id: UUID = Field(default_factory=uuid4)
    broker_session_id: UUID
    market_data_subscription_id: UUID
    account_reference: str = Field(min_length=1, max_length=180)
    canonical_symbol: str = Field(min_length=1, max_length=80)
    side: OrderSide
    order_type: OrderType
    time_in_force: TimeInForce = TimeInForce.gtc
    volume: float = Field(gt=0)
    requested_price: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    max_slippage_points: float = Field(default=0, ge=0)
    strategy_id: str = Field(min_length=1, max_length=120)
    observation: OrderRoutingObservation = Field(default_factory=OrderRoutingObservation)
    risk_brain_clear: bool = True
    policy: OrderRoutingPolicy = Field(default_factory=OrderRoutingPolicy)


class OrderIntent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    intent_id: UUID
    broker_session_id: UUID
    market_data_subscription_id: UUID
    account_reference: str
    canonical_symbol: str
    side: OrderSide
    order_type: OrderType
    time_in_force: TimeInForce
    volume: float
    requested_price: float | None
    stop_loss: float | None
    take_profit: float | None
    max_slippage_points: float
    strategy_id: str
    state: OrderRoutingState
    pretrade_approved: bool
    dispatch_allowed: bool
    recommended_action: str
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    intent_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    approved: bool = True


class OrderRoutingStatusResponse(BaseModel):
    workspace_id: str
    intents: int
    ready_for_dispatch: int
    blocked_or_rejected: int
    latest_state: OrderRoutingState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    intent_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
