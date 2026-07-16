import pytest

from app.tradingview_sync.models import ChartFrameCreate, TradingViewWebhook, WatchItem, WatchlistCreate
from app.tradingview_sync.service import TradingViewSyncError, tradingview_sync_service


def setup_function() -> None:
    tradingview_sync_service.reset()
    tradingview_sync_service.set_webhook_secret("secret-123")


def test_watchlist_supports_mt5_sync_and_multiple_timeframes() -> None:
    record = tradingview_sync_service.create_watchlist(
        WatchlistCreate(name="Gold", items=[WatchItem(symbol="XAUUSD", timeframe="H1"), WatchItem(symbol="XAUUSD", timeframe="M15")])
    )
    assert len(record.items) == 2
    assert tradingview_sync_service.status().mt5_sync_enabled is True


def test_webhook_requires_secret_and_never_enables_execution() -> None:
    with pytest.raises(TradingViewSyncError, match="secret"):
        tradingview_sync_service.receive_webhook(
            TradingViewWebhook(secret="wrong-000", symbol="EURUSD", timeframe="M15", price=1.1, alert_name="BOS")
        )
    alert = tradingview_sync_service.receive_webhook(
        TradingViewWebhook(secret="secret-123", symbol="EURUSD", timeframe="M15", price=1.1, alert_name="BOS", zone_low=1.09, zone_high=1.11)
    )
    assert alert.order_execution_enabled is False


def test_chart_frames_support_multi_monitor_layout() -> None:
    frame = tradingview_sync_service.add_frame(
        ChartFrameCreate(symbol="XAUUSD", timeframe="M5", image_ref="frames/xau.png", monitor=3)
    )
    assert frame.monitor == 3
    assert tradingview_sync_service.status().frames == 1


def test_status_contract_is_advisory_only() -> None:
    status = tradingview_sync_service.status()
    assert status.automatic_order_execution is False
