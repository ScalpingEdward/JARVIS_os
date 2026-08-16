from pathlib import Path

import pytest

from app.core.auron_integration_readiness_v21_532 import get_integration_readiness
from app.trading.auron_strategy_signal_intake_v21_532 import (
    SignalIntakeError,
    StrategySignalIntake,
    make_signal,
)


def intake(tmp_path: Path) -> StrategySignalIntake:
    return StrategySignalIntake(tmp_path / 'signals.sqlite3')


def test_valid_signal_persists_without_execution(tmp_path: Path) -> None:
    store = intake(tmp_path)
    signal = make_signal(strategy_id='ict-gold', source='manual', symbol='XAUUSD', side='buy', signal_type='market', stop_loss=2388.0, take_profit=2415.0, risk_pct=0.5, rationale='liquidity sweep + FVG')
    record = store.ingest(signal)
    assert record.state == 'validated'
    assert record.execution_state == 'not-dispatched'
    assert record.external_calls_made == 0
    reopened = StrategySignalIntake(tmp_path / 'signals.sqlite3')
    assert reopened.get(signal.signal_id) == record


def test_duplicate_signal_is_idempotent(tmp_path: Path) -> None:
    store = intake(tmp_path)
    signal = make_signal(signal_id='same', strategy_id='s1', source='test', symbol='EURUSD', side='sell', signal_type='market', stop_loss=1.1, rationale='test')
    first = store.ingest(signal)
    second = store.ingest(signal)
    assert first == second


def test_duplicate_id_with_different_payload_is_blocked(tmp_path: Path) -> None:
    store = intake(tmp_path)
    first = make_signal(signal_id='same', strategy_id='s1', source='test', symbol='EURUSD', side='sell', signal_type='market', stop_loss=1.1, rationale='one')
    second = make_signal(signal_id='same', strategy_id='s1', source='test', symbol='EURUSD', side='buy', signal_type='market', stop_loss=1.1, rationale='two')
    store.ingest(first)
    with pytest.raises(SignalIntakeError, match='different payload'):
        store.ingest(second)


def test_invalid_signal_is_persisted_as_rejected_and_cannot_advance(tmp_path: Path) -> None:
    store = intake(tmp_path)
    signal = make_signal(strategy_id='bad', source='test', symbol='XAUUSD', side='buy', signal_type='limit', stop_loss=2300.0, rationale='missing entry')
    record = store.ingest(signal)
    assert record.state == 'rejected'
    with pytest.raises(SignalIntakeError, match='validated'):
        store.mark_for_risk_evaluation(signal.signal_id)


def test_valid_signal_can_only_advance_to_risk_evaluation_not_execution(tmp_path: Path) -> None:
    store = intake(tmp_path)
    signal = make_signal(strategy_id='s1', source='replay', symbol='GBPUSD', side='buy', signal_type='limit', entry_price=1.28, stop_loss=1.27, take_profit=1.30, risk_pct=0.5, rationale='replay')
    store.ingest(signal)
    advanced = store.mark_for_risk_evaluation(signal.signal_id)
    assert advanced.execution_state == 'pending-risk-evaluation'
    assert advanced.external_calls_made == 0


def test_b3_advances_exactly_to_b4() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.532'
    assert readiness['current_item'] == 'B3-strategy-signal-intake-separated-from-execution'
    assert readiness['next_item'] == 'B4-pre-trade-risk-engine'
    assert readiness['trading_live_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
