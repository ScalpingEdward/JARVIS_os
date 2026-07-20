from uuid import uuid4

import pytest

from app.executive_market_data.models import (
    FeedKind,
    MarketDataObservation,
    MarketDataState,
    MarketDataSubscriptionCreate,
    RecoverStreamRequest,
    StreamKind,
    SymbolMapping,
)
from app.executive_market_data.service import executive_market_data_service


@pytest.fixture(autouse=True)
def reset_service() -> None:
    executive_market_data_service.reset()


def payload(**changes):
    base = dict(
        workspace_id="ws-1",
        source_key="feed-1",
        actor_id="operator",
        broker_session_id=uuid4(),
        feed_id="mt5-primary",
        feed_kind=FeedKind.mt5,
        stream_kind=StreamKind.tick,
        mapping=SymbolMapping(canonical_symbol="XAUUSD", provider_symbol="XAUUSD", asset_class="metal"),
    )
    base.update(changes)
    return MarketDataSubscriptionCreate(**base)


def test_ready_stream() -> None:
    record = executive_market_data_service.subscribe(payload())
    assert record.state == MarketDataState.stream_ready
    assert record.stream_ready is True


def test_unknown_symbol() -> None:
    observation = MarketDataObservation(symbol_registered=False)
    record = executive_market_data_service.subscribe(payload(observation=observation))
    assert record.state == MarketDataState.symbol_unknown


def test_feed_unavailable() -> None:
    observation = MarketDataObservation(feed_available=False)
    record = executive_market_data_service.subscribe(payload(observation=observation))
    assert record.state == MarketDataState.feed_unavailable


def test_gap_and_recovery() -> None:
    observation = MarketDataObservation(gap_detected=True)
    record = executive_market_data_service.subscribe(payload(observation=observation))
    assert record.state == MarketDataState.gap_detected
    recovered = executive_market_data_service.recover(RecoverStreamRequest(workspace_id="ws-1", subscription_id=record.subscription_id, actor_id="operator"))
    assert recovered.state == MarketDataState.stream_ready


def test_invalid_price() -> None:
    observation = MarketDataObservation(zero_or_negative_price=True)
    record = executive_market_data_service.subscribe(payload(observation=observation))
    assert record.state == MarketDataState.invalid_market_data


def test_latency_exceeded() -> None:
    observation = MarketDataObservation(latency_ms=1001)
    record = executive_market_data_service.subscribe(payload(observation=observation))
    assert record.state == MarketDataState.latency_exceeded


def test_risk_brain_block() -> None:
    record = executive_market_data_service.subscribe(payload(risk_brain_clear=False))
    assert record.state == MarketDataState.blocked


def test_duplicate_subscription_rejected() -> None:
    subscription_id = uuid4()
    executive_market_data_service.subscribe(payload(subscription_id=subscription_id))
    with pytest.raises(ValueError):
        executive_market_data_service.subscribe(payload(source_key="feed-2", subscription_id=subscription_id))


def test_workspace_isolation() -> None:
    record = executive_market_data_service.subscribe(payload())
    assert executive_market_data_service.get(record.id, "ws-2") is None
    assert executive_market_data_service.list_subscriptions("ws-2") == []
