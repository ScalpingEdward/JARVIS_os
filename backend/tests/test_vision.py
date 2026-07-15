import pytest

from app.vision.models import LiveFeedCreate, LiveFrameIngest, VisionFrameCreate, VisionSource
from app.vision.service import VisionError, vision_service


def setup_function() -> None:
    vision_service.reset()


def test_screenshot_analysis_is_advisory_only() -> None:
    result = vision_service.analyze(
        VisionFrameCreate(
            source=VisionSource.upload,
            image_ref="memory://chart.png",
            symbol="XAUUSD",
            timeframe="M15",
        )
    )
    assert result.advisory_only is True
    assert result.order_execution_allowed is False
    assert result.frame.symbol == "XAUUSD"


def test_tradingview_live_feed_accepts_frames() -> None:
    feed = vision_service.create_feed(
        LiveFeedCreate(source=VisionSource.tradingview, name="Gold chart", symbol="XAUUSD", timeframe="M5")
    )
    analysis = vision_service.ingest_live_frame(feed.id, LiveFrameIngest(image_ref="stream://frame-1"))
    updated = vision_service.list_feeds()[0]
    assert analysis.frame.source == VisionSource.tradingview
    assert updated.frame_count == 1
    assert updated.last_frame_at is not None


def test_mt5_live_feed_is_supported_without_order_execution() -> None:
    feed = vision_service.create_feed(
        LiveFeedCreate(source=VisionSource.mt5, name="MT5 terminal", symbol="EURUSD", timeframe="H1")
    )
    analysis = vision_service.ingest_live_frame(feed.id, LiveFrameIngest(image_ref="mt5://screenshot-1"))
    assert analysis.frame.source == VisionSource.mt5
    assert analysis.order_execution_allowed is False


def test_telegram_cannot_be_registered_as_live_feed() -> None:
    with pytest.raises(VisionError, match="only supported"):
        vision_service.create_feed(LiveFeedCreate(source=VisionSource.telegram, name="chat"))


def test_status_exposes_live_capability_and_safety_contract() -> None:
    status = vision_service.status()
    assert VisionSource.tradingview in status.supported_sources
    assert VisionSource.mt5 in status.supported_sources
    assert status.advisory_only is True
    assert status.automatic_order_execution is False
