from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MarketDataState(str, Enum):
    blocked = "blocked"
    symbol_unknown = "symbol-unknown"
    feed_unavailable = "feed-unavailable"
    stream_degraded = "stream-degraded"
    gap_detected = "gap-detected"
    invalid_market_data = "invalid-market-data"
    latency_exceeded = "latency-exceeded"
    market_open = "market-open"
    market_closed = "market-closed"
    stream_ready = "stream-ready"


class FeedKind(str, Enum):
    mt5 = "mt5"
    mt4 = "mt4"
    dxtrade = "dxtrade"
    ctrader = "ctrader"
    interactive_brokers = "interactive-brokers"
    fix_gateway = "fix-gateway"
    rest = "rest"
    paper = "paper"
    historical = "historical"


class StreamKind(str, Enum):
    tick = "tick"
    candle = "candle"
    spread = "spread"
    level_two = "level-two"


class SymbolMapping(BaseModel):
    canonical_symbol: str = Field(min_length=1, max_length=80)
    provider_symbol: str = Field(min_length=1, max_length=80)
    asset_class: str = Field(min_length=1, max_length=60)
    timezone: str = Field(default="UTC", min_length=1, max_length=80)
    price_precision: int = Field(default=5, ge=0, le=12)
    volume_precision: int = Field(default=2, ge=0, le=12)


class MarketDataObservation(BaseModel):
    broker_session_state: str = Field(default="session-ready", min_length=1, max_length=40)
    symbol_registered: bool = True
    symbol_mapping_valid: bool = True
    instrument_discovery_complete: bool = True
    feed_available: bool = True
    stream_connected: bool = True
    heartbeat_fresh: bool = True
    market_open: bool = True
    sequence_valid: bool = True
    duplicate_tick_detected: bool = False
    gap_detected: bool = False
    replay_available: bool = True
    recovery_acknowledged: bool = True
    timestamp_valid: bool = True
    clock_drift_ms: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    zero_or_negative_price: bool = False
    outlier_detected: bool = False
    spread_valid: bool = True
    volume_valid: bool = True
    candle_integrity_valid: bool = True
    failover_feed_available: bool = True


class MarketDataPolicy(BaseModel):
    require_ready_broker_session: bool = True
    require_registered_symbol: bool = True
    require_valid_mapping: bool = True
    require_instrument_discovery: bool = True
    require_available_feed: bool = True
    require_connected_stream: bool = True
    require_fresh_heartbeat: bool = True
    require_valid_sequence: bool = True
    reject_duplicate_ticks: bool = True
    reject_gaps: bool = True
    require_replay_for_recovery: bool = True
    require_recovery_ack: bool = True
    require_valid_timestamps: bool = True
    max_clock_drift_ms: int = Field(default=1000, ge=0)
    max_latency_ms: int = Field(default=1000, ge=0)
    reject_invalid_prices: bool = True
    reject_outliers: bool = True
    require_valid_spread: bool = True
    require_valid_volume: bool = True
    require_candle_integrity: bool = True


class MarketDataSubscriptionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    subscription_id: UUID = Field(default_factory=uuid4)
    broker_session_id: UUID
    feed_id: str = Field(min_length=1, max_length=120)
    feed_kind: FeedKind
    stream_kind: StreamKind
    mapping: SymbolMapping
    timeframe: str | None = Field(default=None, max_length=20)
    observation: MarketDataObservation = Field(default_factory=MarketDataObservation)
    risk_brain_clear: bool = True
    policy: MarketDataPolicy = Field(default_factory=MarketDataPolicy)


class MarketDataSubscription(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    subscription_id: UUID
    broker_session_id: UUID
    feed_id: str
    feed_kind: FeedKind
    stream_kind: StreamKind
    mapping: SymbolMapping
    timeframe: str | None
    state: MarketDataState
    stream_ready: bool
    recovery_required: bool
    failover_available: bool
    recommended_action: str
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MarketDataStatusResponse(BaseModel):
    workspace_id: str
    subscriptions: int
    stream_ready: int
    degraded_or_blocked: int
    latest_state: MarketDataState | None
    autonomous_actions_enabled: bool = False


class RecoverStreamRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    subscription_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    replay_completed: bool = True
    recovery_acknowledged: bool = True


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    subscription_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
