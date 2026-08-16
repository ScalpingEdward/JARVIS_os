from pathlib import Path

import pytest

from app.core.auron_integration_readiness_v21_531 import get_integration_readiness
from app.trading.auron_trading_account_state_v21_531 import (
    NormalizedOrder,
    NormalizedPosition,
    TradingAccountStateStore,
    TradingStateError,
    make_manual_snapshot,
)
from app.trading.auron_trading_registry_v21_530 import (
    ProviderRuleProfile,
    TradingAccount,
    TradingAccountRegistry,
)


def setup_registry(tmp_path: Path) -> TradingAccountRegistry:
    registry = TradingAccountRegistry(tmp_path / 'registry.sqlite3')
    registry.upsert_rule_profile(ProviderRuleProfile('Firm','default',5,10,8,4,None,None,True,False,True,True,False,None,None,''))
    registry.register_account(TradingAccount('a1','Firm','ref-1','100K-A','evaluation','active','USD',100000,'default'))
    return registry


def test_snapshot_requires_registered_account(tmp_path: Path) -> None:
    registry = TradingAccountRegistry(tmp_path / 'registry.sqlite3')
    store = TradingAccountStateStore(tmp_path / 'state.sqlite3', registry)
    with pytest.raises(TradingStateError, match='B1 registry'):
        store.upsert_snapshot(make_manual_snapshot(account_id='missing', balance=100000, equity=100000, floating_pnl=0, realized_pnl=0))


def test_normalized_snapshot_persists_positions_orders_and_day_state(tmp_path: Path) -> None:
    registry = setup_registry(tmp_path)
    store = TradingAccountStateStore(tmp_path / 'state.sqlite3', registry)
    state = make_manual_snapshot(
        account_id='a1', balance=100500, equity=100650, floating_pnl=150, realized_pnl=500,
        gross_exposure=3200, net_exposure=1200, margin_used=450, free_margin=100200,
        positions=(NormalizedPosition('p1','XAUUSD','buy',0.5,2400,2403,150,2395,2420),),
        orders=(NormalizedOrder('o1','EURUSD','buy','limit',1.0,1.08,'pending'),),
        trading_date='2026-08-16', trading_day_realized_pnl=250, trading_day_start_balance=100250,
        trades_closed=3, trading_day_counted=True,
    )
    stored = store.upsert_snapshot(state)
    assert stored.account_id == 'a1'
    assert stored.equity == 100650
    assert stored.floating_pnl == 150
    assert stored.positions[0].symbol == 'XAUUSD'
    assert stored.orders[0].status == 'pending'
    assert stored.trading_day.trades_closed == 3
    assert stored.trading_day.trading_day_counted is True


def test_snapshot_replacement_is_atomic_for_positions_and_orders(tmp_path: Path) -> None:
    registry = setup_registry(tmp_path)
    store = TradingAccountStateStore(tmp_path / 'state.sqlite3', registry)
    first = make_manual_snapshot(account_id='a1', balance=100000, equity=100100, floating_pnl=100, realized_pnl=0, positions=(NormalizedPosition('p1','XAUUSD','buy',0.1,2400,2401,10),), orders=(NormalizedOrder('o1','EURUSD','sell','stop',0.2,1.07,'pending'),))
    store.upsert_snapshot(first)
    second = make_manual_snapshot(account_id='a1', balance=100020, equity=100020, floating_pnl=0, realized_pnl=20)
    stored = store.upsert_snapshot(second)
    assert stored.positions == ()
    assert stored.orders == ()
    assert stored.realized_pnl == 20


def test_state_survives_store_reopen(tmp_path: Path) -> None:
    registry = setup_registry(tmp_path)
    db = tmp_path / 'state.sqlite3'
    TradingAccountStateStore(db, registry).upsert_snapshot(make_manual_snapshot(account_id='a1', balance=100000, equity=99900, floating_pnl=-100, realized_pnl=0))
    reopened = TradingAccountStateStore(db, registry)
    assert reopened.get_snapshot('a1') is not None
    assert reopened.get_snapshot('a1').equity == 99900


def test_invalid_negative_financial_state_fails_closed(tmp_path: Path) -> None:
    registry = setup_registry(tmp_path)
    store = TradingAccountStateStore(tmp_path / 'state.sqlite3', registry)
    with pytest.raises(TradingStateError):
        store.upsert_snapshot(make_manual_snapshot(account_id='a1', balance=100000, equity=-1, floating_pnl=0, realized_pnl=0))


def test_b2_advances_exactly_to_b3_without_live_execution() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.531'
    assert readiness['current_item'] == 'B2-normalized-trading-account-state'
    assert readiness['next_item'] == 'B3-strategy-signal-intake'
    assert readiness['core_next_gate'] == 'strategy-signal-intake'
    assert readiness['trading_live_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
