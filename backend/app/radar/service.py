from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AssetClass,
    MarketCreate,
    MarketRecord,
    RadarPriority,
    RadarStatus,
    ResearchEvent,
    ResearchEventCreate,
    WatchMode,
)


CORE_MARKETS = (
    ("XAUUSD", AssetClass.metal, RadarPriority.critical),
    ("EURUSD", AssetClass.forex, RadarPriority.high),
    ("GBPUSD", AssetClass.forex, RadarPriority.normal),
    ("USDJPY", AssetClass.forex, RadarPriority.normal),
    ("NAS100", AssetClass.index, RadarPriority.critical),
    ("SPX500", AssetClass.index, RadarPriority.normal),
    ("US30", AssetClass.index, RadarPriority.normal),
    ("BTCUSD", AssetClass.crypto, RadarPriority.high),
)


class RadarService:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._markets: dict[UUID, MarketRecord] = {}
        self._events: dict[UUID, ResearchEvent] = {}
        for symbol, asset_class, priority in CORE_MARKETS:
            record = MarketRecord(
                symbol=symbol,
                asset_class=asset_class,
                priority=priority,
                reason="PHOENIX core market",
                mode=WatchMode.permanent,
                core=True,
            )
            self._markets[record.id] = record

    def add_market(self, payload: MarketCreate) -> MarketRecord:
        record = MarketRecord(**payload.model_dump())
        self._markets[record.id] = record
        return record

    def list_markets(self, active_only: bool = False) -> list[MarketRecord]:
        self.expire_temporary_watches()
        items = list(self._markets.values())
        if active_only:
            items = [item for item in items if item.active]
        return sorted(items, key=lambda item: (int(item.priority), item.symbol))

    def remove_market(self, market_id: UUID) -> bool:
        item = self._markets.get(market_id)
        if item is None or item.core:
            return False
        del self._markets[market_id]
        return True

    def expire_temporary_watches(self) -> None:
        now = datetime.now(timezone.utc)
        for market in self._markets.values():
            expiry = market.expires_at
            if expiry is not None:
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry <= now:
                    market.active = False
                    market.mode = WatchMode.background

    def add_event(self, payload: ResearchEventCreate) -> ResearchEvent:
        event = ResearchEvent(**payload.model_dump())
        self._events[event.id] = event
        return event

    def list_events(self, minimum_relevance: int = 0) -> list[ResearchEvent]:
        return sorted(
            [event for event in self._events.values() if event.relevance >= minimum_relevance],
            key=lambda event: (event.relevance, event.created_at),
            reverse=True,
        )

    def status(self) -> RadarStatus:
        markets = self.list_markets()
        return RadarStatus(
            core_markets=sum(item.core for item in markets),
            additional_markets=sum(not item.core for item in markets),
            active_markets=sum(item.active for item in markets),
            research_events=len(self._events),
        )

    def export_obsidian(self) -> str:
        lines = ["# PHOENIX Market Radar", "", "## Active markets"]
        for market in self.list_markets(active_only=True):
            lines.append(
                f"- **{market.symbol}** | P{int(market.priority)} | {market.mode.value} | {market.reason}"
            )
        lines.extend(["", "## Research events"])
        for event in self.list_events():
            lines.append(f"- **{event.symbol}** [{event.relevance}/100] {event.headline} — {event.source}")
        return "\n".join(lines) + "\n"


radar_service = RadarService()
