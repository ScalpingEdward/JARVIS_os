from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SessionNewsState(str, Enum):
    BLOCKED = "blocked"
    PENDING_ORDER_REQUIRED = "pending-order-required"
    CLOCK_UNSYNCED = "clock-unsynced"
    SESSION_CLOSED = "session-closed"
    ROLLOVER_BLOCKED = "rollover-blocked"
    MARKET_CLOSED = "market-closed"
    NEWS_DATA_STALE = "news-data-stale"
    NEWS_BLACKOUT = "news-blackout"
    SPREAD_REJECTED = "spread-rejected"
    LIQUIDITY_REJECTED = "liquidity-rejected"
    RISK_REJECTED = "risk-rejected"
    APPROVAL_REQUIRED = "approval-required"
    WINDOW_READY = "window-ready"
    FAILED = "failed"


class SessionNewsAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=40)
    evaluated_at: datetime
    pending_order_ready: bool = False
    clock_synchronized: bool = False
    clock_drift_seconds: float = 0.0
    max_clock_drift_seconds: float = 2.0
    session_name: str = "default"
    session_open: bool = False
    market_open: bool = False
    rollover_window: bool = False
    news_feed_connected: bool = False
    news_snapshot_age_seconds: int = 0
    max_news_snapshot_age_seconds: int = 300
    impacted_currency: bool = False
    high_impact_event: bool = False
    event_time: datetime | None = None
    blackout_before_minutes: int = 15
    blackout_after_minutes: int = 15
    current_spread_points: float = 0.0
    maximum_spread_points: float = 0.0
    liquidity_score: float = 1.0
    minimum_liquidity_score: float = 0.0
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    risk_brain_blocked: bool = False
    human_approved: bool = False
    terminal_error: str | None = None


class SessionNewsExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    human_approved: bool | None = None
    news_feed_connected: bool | None = None
    news_snapshot_age_seconds: int | None = None
    market_open: bool | None = None
    session_open: bool | None = None
    current_spread_points: float | None = None
    liquidity_score: float | None = None
    terminal_error: str | None = None


class SessionNewsAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    state: SessionNewsState
    reasons: list[str] = Field(default_factory=list)
    payload: SessionNewsAssessmentCreate


class SessionNewsStatus(BaseModel):
    workspace_id: str
    latest_state: SessionNewsState | None = None
    count: int = 0


class AuditRecord(BaseModel):
    workspace_id: str
    action: str
    actor_id: str
    record_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
