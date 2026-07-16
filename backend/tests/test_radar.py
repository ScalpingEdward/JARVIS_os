from datetime import datetime, timedelta, timezone

from app.radar.models import AssetClass, MarketCreate, RadarPriority, ResearchEventCreate, WatchMode
from app.radar.service import radar_service


def setup_function() -> None:
    radar_service.reset()


def test_core_markets_are_loaded() -> None:
    markets = radar_service.list_markets()
    assert len(markets) == 8
    assert {item.symbol for item in markets} == {
        "XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "NAS100", "SPX500", "US30", "BTCUSD"
    }
    assert radar_service.status().automatic_order_execution is False


def test_dynamic_and_temporary_watchlists() -> None:
    market = radar_service.add_market(
        MarketCreate(
            symbol="NVDA",
            asset_class=AssetClass.equity,
            priority=RadarPriority.high,
            reason="AI earnings watch",
            mode=WatchMode.temporary,
            expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        )
    )
    assert market.core is False
    assert radar_service.status().additional_markets == 1
    assert radar_service.remove_market(market.id) is True


def test_core_market_cannot_be_removed() -> None:
    core = next(item for item in radar_service.list_markets() if item.core)
    assert radar_service.remove_market(core.id) is False


def test_research_relevance_and_obsidian_export() -> None:
    radar_service.add_event(
        ResearchEventCreate(
            symbol="NVDA",
            category="partnership",
            headline="New AI infrastructure partnership",
            source="public-feed",
            relevance=91,
            summary="Material public announcement",
        )
    )
    assert len(radar_service.list_events(minimum_relevance=90)) == 1
    markdown = radar_service.export_obsidian()
    assert "PHOENIX Market Radar" in markdown
    assert "New AI infrastructure partnership" in markdown
