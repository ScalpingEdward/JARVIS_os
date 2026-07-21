from datetime import datetime, timedelta, timezone

import pytest

from app.executive_mt5_trading_session_news_filter.models import SessionNewsAssessmentCreate, SessionNewsExecuteRequest, SessionNewsState
from app.executive_mt5_trading_session_news_filter.service import TradingSessionNewsFilterService


def payload(**updates):
    base = dict(
        workspace_id="ws-a",
        source_key="source-1",
        actor_id="tester",
        symbol="XAUUSD",
        evaluated_at=datetime.now(timezone.utc),
        pending_order_ready=True,
        clock_synchronized=True,
        session_name="new-york",
        session_open=True,
        market_open=True,
        news_feed_connected=True,
        news_snapshot_age_seconds=20,
        maximum_spread_points=40,
        current_spread_points=15,
        liquidity_score=0.9,
        minimum_liquidity_score=0.5,
        account_risk_approved=True,
        prop_rules_approved=True,
        human_approved=True,
    )
    base.update(updates)
    return SessionNewsAssessmentCreate(**base)


def test_window_ready():
    record = TradingSessionNewsFilterService().create(payload())
    assert record.state == SessionNewsState.WINDOW_READY


def test_requires_pending_order_dependency():
    record = TradingSessionNewsFilterService().create(payload(pending_order_ready=False))
    assert record.state == SessionNewsState.PENDING_ORDER_REQUIRED


def test_clock_drift_blocks():
    record = TradingSessionNewsFilterService().create(payload(clock_drift_seconds=4, max_clock_drift_seconds=2))
    assert record.state == SessionNewsState.CLOCK_UNSYNCED


def test_closed_session_blocks():
    record = TradingSessionNewsFilterService().create(payload(session_open=False))
    assert record.state == SessionNewsState.SESSION_CLOSED


def test_rollover_blocks():
    record = TradingSessionNewsFilterService().create(payload(rollover_window=True))
    assert record.state == SessionNewsState.ROLLOVER_BLOCKED


def test_stale_news_blocks():
    record = TradingSessionNewsFilterService().create(payload(news_snapshot_age_seconds=600, max_news_snapshot_age_seconds=300))
    assert record.state == SessionNewsState.NEWS_DATA_STALE


def test_high_impact_news_blackout_blocks():
    now = datetime.now(timezone.utc)
    record = TradingSessionNewsFilterService().create(payload(evaluated_at=now, impacted_currency=True, high_impact_event=True, event_time=now + timedelta(minutes=5)))
    assert record.state == SessionNewsState.NEWS_BLACKOUT


def test_spread_and_liquidity_gates():
    service = TradingSessionNewsFilterService()
    assert service.create(payload(source_key="spread", current_spread_points=50)).state == SessionNewsState.SPREAD_REJECTED
    assert service.create(payload(source_key="liquidity", liquidity_score=0.2)).state == SessionNewsState.LIQUIDITY_REJECTED


def test_risk_brain_hard_block():
    record = TradingSessionNewsFilterService().create(payload(risk_brain_blocked=True))
    assert record.state == SessionNewsState.BLOCKED


def test_human_approval_and_execute():
    service = TradingSessionNewsFilterService()
    record = service.create(payload(human_approved=False))
    assert record.state == SessionNewsState.APPROVAL_REQUIRED
    updated = service.execute(record.id, "ws-a", SessionNewsExecuteRequest(actor_id="approver", human_approved=True))
    assert updated.state == SessionNewsState.WINDOW_READY


def test_duplicate_source_key_rejected():
    service = TradingSessionNewsFilterService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())


def test_workspace_isolation():
    service = TradingSessionNewsFilterService()
    record = service.create(payload())
    assert service.get(record.id, "ws-b") is None
    assert service.list_records("ws-b") == []
