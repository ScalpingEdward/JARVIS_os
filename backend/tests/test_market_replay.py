from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.market_replay.models import Candle, ReplaySessionCreate, ReplayState
from app.market_replay.service import MarketReplayService


def candles(count: int = 4) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            timestamp=start + timedelta(minutes=index),
            open=100 + index,
            high=102 + index,
            low=99 + index,
            close=101 + index,
            volume=10,
        )
        for index in range(count)
    ]


def test_create_and_step_replay_session() -> None:
    service = MarketReplayService()
    session = service.create(
        ReplaySessionCreate(symbol="xauusd", timeframe="m1", candles=candles())
    )
    assert session.symbol == "XAUUSD"
    stepped = service.step(session.id, 2)
    assert stepped is not None
    assert stepped.cursor == 2
    assert stepped.state == ReplayState.RUNNING


def test_replay_completes_at_last_bar() -> None:
    service = MarketReplayService()
    session = service.create(
        ReplaySessionCreate(symbol="EURUSD", timeframe="M5", candles=candles(3))
    )
    completed = service.step(session.id, 10)
    assert completed is not None
    assert completed.cursor == 3
    assert completed.state == ReplayState.COMPLETED


def test_pause_resume_and_cancel() -> None:
    service = MarketReplayService()
    session = service.create(
        ReplaySessionCreate(symbol="BTCUSD", timeframe="M1", candles=candles())
    )
    service.step(session.id, 1)
    assert service.pause(session.id).state == ReplayState.PAUSED
    assert service.resume(session.id).state == ReplayState.RUNNING
    assert service.cancel(session.id).state == ReplayState.CANCELLED


def test_report_contains_progress_and_master_brano_recommendation() -> None:
    service = MarketReplayService()
    session = service.create(
        ReplaySessionCreate(symbol="NAS100", timeframe="M15", candles=candles())
    )
    service.step(session.id, 2)
    report = service.report(session.id)
    assert report is not None
    assert report.progress_pct == 50.0
    assert report.current_price == 102
    assert "MASTER Brano" in report.recommendation


def test_automatic_execution_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ReplaySessionCreate(
            symbol="XAUUSD",
            timeframe="M1",
            candles=candles(),
            automatic_execution=True,
        )


def test_non_chronological_candles_are_rejected() -> None:
    data = candles()
    data[1] = data[0]
    with pytest.raises(ValidationError):
        ReplaySessionCreate(symbol="XAUUSD", timeframe="M1", candles=data)
