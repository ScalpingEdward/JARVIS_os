from pathlib import Path

import pytest

from app.core.auron_integration_readiness_v21_534 import get_integration_readiness
from app.trading.auron_multi_account_allocation_v21_534 import InstrumentSizingSpec, MultiAccountAllocationEngine
from app.trading.auron_pre_trade_risk_engine_v21_533 import PreTradeRiskEngine, RiskPolicy
from app.trading.auron_strategy_signal_intake_v21_532 import StrategySignalIntake, make_signal
from app.trading.auron_trading_account_state_v21_531 import TradingAccountStateStore, make_manual_snapshot
from app.trading.auron_trading_registry_v21_530 import ProviderRuleProfile, TradingAccount, TradingAccountRegistry


def setup_stack(tmp_path: Path):
    registry = TradingAccountRegistry(tmp_path / 'registry.sqlite3')
    registry.upsert_rule_profile(ProviderRuleProfile('Firm','default',5.0,10.0,8.0,4,None,None,True,False,True,True,False,None,None,''))
    registry.register_account(TradingAccount('a100','Firm','r100','100K','evaluation','active','USD',100000,'default'))
    registry.register_account(TradingAccount('a200','Firm','r200','200K','evaluation','active','USD',200000,'default'))
    states = TradingAccountStateStore(tmp_path / 'state.sqlite3', registry)
    states.upsert_snapshot(make_manual_snapshot(account_id='a100', balance=100000, equity=100000, floating_pnl=0, realized_pnl=0))
    states.upsert_snapshot(make_manual_snapshot(account_id='a200', balance=200000, equity=198000, floating_pnl=-2000, realized_pnl=0, trading_day_start_balance=200000))
    signals = StrategySignalIntake(tmp_path / 'signals.sqlite3')
    signal = make_signal(signal_id='sig-xau', strategy_id='ict-gold', source='test', symbol='XAUUSD', side='buy', signal_type='market', stop_loss=2380.0, take_profit=2420.0, risk_pct=0.5, rationale='test')
    signals.ingest(signal)
    signals.mark_for_risk_evaluation(signal.signal_id)
    risk = PreTradeRiskEngine(registry, states, signals, RiskPolicy(max_risk_per_trade_pct=0.5))
    return signals, risk


def test_allocation_sizes_each_account_from_its_own_permitted_risk(tmp_path: Path) -> None:
    signals, risk = setup_stack(tmp_path)
    engine = MultiAccountAllocationEngine(signals, risk)
    spec = InstrumentSizingSpec('XAUUSD', value_per_price_unit_per_lot=100.0, min_lot=0.01, max_lot=20.0, lot_step=0.01)
    batch = engine.allocate('sig-xau', reference_price=2400.0, sizing_spec=spec)
    assert batch.approved_accounts == ('a100', 'a200')
    by_account = {c.account_id: c for c in batch.child_intents}
    assert by_account['a100'].calculated_lot == pytest.approx(0.25)
    assert by_account['a200'].calculated_lot == pytest.approx(0.49)
    assert by_account['a100'].calculated_lot != by_account['a200'].calculated_lot
    assert batch.external_calls_made == 0


def test_account_with_exhausted_risk_headroom_is_not_copied(tmp_path: Path) -> None:
    signals, risk = setup_stack(tmp_path)
    risk.states.upsert_snapshot(make_manual_snapshot(account_id='a200', balance=200000, equity=190000, floating_pnl=-10000, realized_pnl=0, trading_day_start_balance=200000))
    engine = MultiAccountAllocationEngine(signals, risk)
    spec = InstrumentSizingSpec('XAUUSD',100.0,0.01,20.0,0.01)
    batch = engine.allocate('sig-xau', reference_price=2400.0, sizing_spec=spec)
    assert 'a100' in batch.approved_accounts
    assert 'a200' in batch.blocked_accounts
    blocked = next(c for c in batch.child_intents if c.account_id == 'a200')
    assert blocked.calculated_lot == 0.0


def test_symbol_mismatch_blocks_child_intents(tmp_path: Path) -> None:
    signals, risk = setup_stack(tmp_path)
    engine = MultiAccountAllocationEngine(signals, risk)
    batch = engine.allocate('sig-xau', reference_price=2400.0, sizing_spec=InstrumentSizingSpec('EURUSD',100000.0,0.01,10.0,0.01))
    assert batch.approved_accounts == ()
    assert set(batch.blocked_accounts) == {'a100','a200'}
    assert all('sizing-spec-symbol-mismatch' in child.blockers for child in batch.child_intents)


def test_lot_is_rounded_down_to_step_and_never_above_risk_budget(tmp_path: Path) -> None:
    signals, risk = setup_stack(tmp_path)
    engine = MultiAccountAllocationEngine(signals, risk)
    child = engine.allocate('sig-xau', reference_price=2393.0, sizing_spec=InstrumentSizingSpec('XAUUSD',100.0,0.01,20.0,0.01)).child_intents[0]
    assert child.calculated_lot == pytest.approx(0.38)
    theoretical_risk = child.calculated_lot * abs(child.reference_price-child.stop_loss) * 100.0
    assert theoretical_risk <= child.risk_amount


def test_b5_advances_exactly_to_b6_without_live_execution() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.534'
    assert readiness['current_item'] == 'B5-multi-account-allocation-copy-engine'
    assert readiness['next_item'] == 'B6-account-session-news-guards-and-kill-switches'
    assert readiness['trading_live_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
