from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BrokerType(str, Enum):
    broker = "broker"
    prop_firm = "prop_firm"


class ConnectorState(str, Enum):
    online = "online"
    degraded = "degraded"
    offline = "offline"
    disabled = "disabled"


class AccountMode(str, Enum):
    funded = "funded"
    challenge = "challenge"
    live = "live"
    demo = "demo"


class BrokerRuleProfile(BaseModel):
    daily_drawdown_pct: float = Field(default=5.0, gt=0, le=100)
    max_drawdown_pct: float = Field(default=10.0, gt=0, le=100)
    news_restriction_minutes: int = Field(default=0, ge=0, le=1440)
    weekend_holding_allowed: bool = True
    expert_advisors_allowed: bool = True
    hedging_allowed: bool = True
    minimum_hold_seconds: int = Field(default=0, ge=0)


class SymbolMapping(BaseModel):
    canonical_symbol: str = Field(min_length=2, max_length=40)
    broker_symbol: str = Field(min_length=2, max_length=40)


class BrokerConnectionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    broker_type: BrokerType = BrokerType.broker
    platform: str = Field(default="MT5", min_length=2, max_length=30)
    read_only: bool = True
    state: ConnectorState = ConnectorState.offline
    latency_ms: int | None = Field(default=None, ge=0)
    rule_profile: BrokerRuleProfile = Field(default_factory=BrokerRuleProfile)
    symbol_mappings: list[SymbolMapping] = Field(default_factory=list)


class BrokerConnection(BrokerConnectionCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat_at: datetime | None = None


class BrokerAccountCreate(BaseModel):
    broker_id: UUID
    external_account_id: str = Field(min_length=2, max_length=100)
    label: str = Field(min_length=2, max_length=80)
    mode: AccountMode
    currency: str = Field(default="USD", min_length=3, max_length=3)
    balance: float = Field(ge=0)
    equity: float = Field(ge=0)
    daily_drawdown_pct: float = Field(default=0, ge=0)
    total_drawdown_pct: float = Field(default=0, ge=0)


class BrokerAccount(BrokerAccountCreate):
    id: UUID = Field(default_factory=uuid4)
    synced_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BrokerFleetStatus(BaseModel):
    owner_name: str = "MASTER Brano"
    brokers: int
    accounts: int
    online_brokers: int
    degraded_brokers: int
    offline_brokers: int
    blocked_accounts: int
    total_balance: float
    total_equity: float
    read_only: bool = True
    automatic_execution: bool = False
    automatic_order_execution: bool = False
    requires_human_approval: bool = True
    recommendations: list[str] = Field(default_factory=list)


class SymbolResolution(BaseModel):
    broker_id: UUID
    canonical_symbol: str
    broker_symbol: str
