from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.replay_intelligence.models import JournalEntryCreate, TradeDirection, TradeOutcome
from app.replay_intelligence.service import ReplayIntelligenceService


def payload(**overrides) -> JournalEntryCreate:
    values = {
        "replay_session_id": uuid4(),
        "symbol": "xauusd",
        "timeframe": "m5",
        "direction": TradeDirection.LONG,
        "entry_price": 2300,
        "exit_price": 2310,
        "risk_amount": 5,
        "fees": 1,
        "setup_tags": ["FVG", " liquidity sweep ", "FVG"],
        "mistakes": [],
    }
    values.update(overrides)
    return JournalEntryCreate(**values)


def test_create_journal_entry_calculates_trade_metrics() -> None:
    service = ReplayIntelligenceService()
    entry = service.create(payload())
    assert entry.symbol == "XAUUSD"
    assert entry.timeframe == "M5"
    assert entry.pnl == 9
    assert entry.r_multiple == 1.8
    assert entry.outcome == TradeOutcome.WIN
    assert entry.setup_tags == ["fvg", "liquidity sweep"]


def test_short_trade_profit_is_calculated_correctly() -> None:
    service = ReplayIntelligenceService()
    entry = service.create(
        payload(direction=TradeDirection.SHORT, entry_price=100, exit_price=90, fees=0)
    )
    assert entry.pnl == 10
    assert entry.outcome == TradeOutcome.WIN


def test_summary_tracks_expectancy_tags_and_mistakes() -> None:
    service = ReplayIntelligenceService()
    replay_id = uuid4()
    service.create(payload(replay_session_id=replay_id, mistakes=["late entry"]))
    service.create(
        payload(
            replay_session_id=replay_id,
            entry_price=100,
            exit_price=95,
            fees=0,
            risk_amount=5,
            setup_tags=["breaker"],
            mistakes=["late entry"],
        )
    )
    summary = service.summary(replay_id)
    assert summary.total_trades == 2
    assert summary.wins == 1
    assert summary.losses == 1
    assert summary.net_pnl == 4
    assert summary.recurring_mistakes == ["late entry"]
    assert "collect at least 10" in summary.recommendation


def test_entries_can_be_filtered_by_replay_session() -> None:
    service = ReplayIntelligenceService()
    wanted = uuid4()
    service.create(payload(replay_session_id=wanted))
    service.create(payload(replay_session_id=uuid4()))
    assert len(service.list_all(wanted)) == 1


def test_automatic_execution_and_missing_approval_are_rejected() -> None:
    with pytest.raises(ValidationError):
        payload(automatic_execution=True)
    with pytest.raises(ValidationError):
        payload(human_approved=False)
