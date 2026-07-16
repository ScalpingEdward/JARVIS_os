from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AssetClass(str, Enum):
    forex = "forex"
    metal = "metal"
    index = "index"
    crypto = "crypto"
    equity = "equity"
    etf = "etf"
    future = "future"
    commodity = "commodity"


class RadarPriority(int, Enum):
    critical = 1
    high = 2
    normal = 3


class WatchMode(str, Enum):
    permanent = "permanent"
    temporary = "temporary"
    session = "session"
    background = "background"


class MarketCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    asset_class: AssetClass
    priority: RadarPriority = RadarPriority.normal
    reason: str = Field(default="manual watch", max_length=500)
    mode: WatchMode = WatchMode.background
    expires_at: datetime | None = None
    active_session: str | None = None


class MarketRecord(MarketCreate):
    id: UUID = Field(default_factory=uuid4)
    core: bool = False
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ResearchEventCreate(BaseModel):
    symbol: str
    category: str
    headline: str
    source: str
    relevance: int = Field(ge=0, le=100)
    summary: str = ""


class ResearchEvent(ResearchEventCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RadarStatus(BaseModel):
    core_markets: int
    additional_markets: int
    active_markets: int
    research_events: int
    automatic_order_execution: bool = False
    obsidian_export_supported: bool = True
