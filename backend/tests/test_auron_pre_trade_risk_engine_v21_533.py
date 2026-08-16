from pathlib import Path

import pytest

from app.core.auron_integration_readiness_v21_533 import get_integration_readiness
from app.trading.auron_pre_trade_risk_engine_v21_533 import PreTradeRiskEngine, PreTradeRiskError, RiskPolicy
from app.trading.auron_strategy_signal_intake_v21_532 import StrategySignalIntake, make_signal
from app.trading.auron_trading_account_state_v21_531 import TradingAccountStateStore, make_manual_snapshot
from app.trading.auron_trading_registry_v21_530 import ProviderRuleProfile, TradingAccount, TradingAccountRegistry


def setup_stack(tmp_path: Path, *, daily_dd: float | None = 5.0, max_dd: float | None = 10.0):
    registry = TradingAccountRegistry(tmp_path / 'registry.sqlite3')
    registry.upsert_rule_profile(ProviderRuleProfile('TestFirm','100k',daily_dd,max_dd,8.0,4,None,None,True,False,True,True,False,None,None,'test'))
    registry.register_account(TradingAccount('acc-1','TestFirm','ref-1','100K','evaluation','active','USD',100000,'100k'))
    states = TradingAccountStateStore(tmp_path / 'state.sqlite3', registry)
    signals = StrategySignalIntake(tmp_path / 'signals.sqlite3')
    return registry, states, signals


def add_signal(signals: StrategySignalIntake, risk_pct: float = 0.5):
    signal = make_signal(signal_id='sig-1', strategy_id='ict-gold', source='test', symbol='XAUUSD', side='buy', signal_type='market', stop_loss=2380.0, take_profit=2420.0, risk_pct=risk_pct, rationale='test setup')
    signals.ingest(signal)
    signals.mark_for_risk_evaluation(signal.signal_id)
    return signal


def test_healthy_account_gets_account_specific_permitted_risk(tmp_path: Path) -> None:
    registry, states, signals = setup_stack(tmp_path)
    states.upsert_snapshot(make_manual_snapshot(account_id='acc-1', balance=100000, equity=99500, floating_pnl=-500, realized_pnl=0, trading_day_start_balance=100000))
    signal = add_signal(signals, 0.5)
    decision = PreTradeRiskEngine(registry, states, signals).evaluate(signal.signal_id, 'acc-1')
    assert decision.state == 'approved-for-allocation'
    assert decision.permitted_risk_pct == pytest.approx(0.5)
    assert decision.permitted_risk_amount == pytest.approx(497.5)
    assert decision.daily_drawdown_used_pct == pytest.approx(0.5)
    assert decision.max_drawdown_used_pct == pytest.approx(0.5)
    assert decision.external_calls_made == 0


def test_requested_risk_is_capped_by_central_b4_policy(tmp_path: Path) -> None:
    registry, states, signals = setup_stack(tmp_path)
    states.upsert_snapshot(make_manual_snapshot(account_id='acc-1', balance=100000, equity=100000, floating_pnl=0, realized_pnl=0))
    signal = add_signal(signals, 2.0)
    decision = PreTradeRiskEngine(registry, states, signals, RiskPolicy(max_risk_per_trade_pct=0.5)).evaluate(signal.signal_id, 'acc-1')
    assert decision.requested_risk_pct == pytest.approx(0.5)
    assert decision.permitted_risk_pct == pytest.approx(0.5)


def test_daily_drawdown_headroom_blocks_before_allocation(tmp_path: Path) -> None:
    registry, states, signals = setup_stack(tmp_path, daily_dd=5.0, max_dd=10.0)
    states.upsert_snapshot(make_manual_snapshot(account_id='acc-1', balance=96000, equity=95250, floating_pnl=-750, realized_pnl=-4000, trading_day_start_balance=100000))
    signal = add_signal(signals)
    decision = PreTradeRiskEngine(registry, states, signals).evaluate(signal.signal_id, 'acc-1')
    assert decision.state == 'blocked'
    assert 'daily-drawdown-headroom-exhausted' in decision.blockers
    assert decision.permitted_risk_amount == 0


def test_max_drawdown_headroom_blocks_before_allocation(tmp_path: Path) -> None:
    registry, states, signals = setup_stack(tmp_path, daily_dd=20.0, max_dd=10.0)
    states.upsert_snapshot(make_manual_snapshot(account_id='acc-1', balance=91000, equity=90400, floating_pnl=-600, realized_pnl=-9000, trading_day_start_balance=91000))
    signal = add_signal(signals)
    decision = PreTradeRiskEngine(registry, states, signals).evaluate(signal.signal_id, 'acc-1')
    assert decision.state == 'blocked'
    assert 'max-drawdown-headroom-exhausted' in decision.blockers


def test_missing_prop_limits_fail_closed(tmp_path: Path) -> None:
    registry, states, signals = setup_stack(tmp_path, daily_dd=None, max_dd=None)
    states.upsert_snapshot(make_manual_snapshot(account_id='acc-1', balance=100000, equity=100000, floating_pnl=0, realized_pnl=0))
    signal = add_signal(signals)
    decision = PreTradeRiskEngine(registry, states, signals).evaluate(signal.signal_id, 'acc-1')
    assert decision.state == 'blocked'
    assert 'daily-drawdown-rule-missing' in decision.blockers
    assert 'max-drawdown-rule-missing' in decision.blockers


def test_missing_normalized_state_fails_closed(tmp_path: Path) -> None:
    registry, states, signals = setup_stack(tmp_path)
    signal = add_signal(signals)
    decision = PreTradeRiskEngine(registry, states, signals).evaluate(signal.signal_id, 'acc-1')
    assert decision.state == 'blocked'
    assert 'normalized-account-state-missing' in decision.blockers


def test_paused_account_is_blocked(tmp_path: Path) -> None:
    registry = TradingAccountRegistry(tmp_path / 'registry.sqlite3')
    registry.upsert_rule_profile(ProviderRuleProfile('Firm','default',5,10,8,4,None,None,True,False,True,True,False,None,None,''))
    registry.register_account(TradingAccount('paused','Firm','ref','Paused','evaluation','paused','USD',100000,'default'))
    states = TradingAccountStateStore(tmp_path / 'state.sqlite3', registry)
    states.upsert_snapshot(make_manual_snapshot(account_id='paused', balance=100000, equity=100000, floating_pnl=0, realized_pnl=0))
    signals = StrategySignalIntake(tmp_path / 'signals.sqlite3')
    signal = make_signal(signal_id='sig', strategy_id='s', source='test', symbol='EURUSD', side='buy', signal_type='market', stop_loss=1.1, risk_pct=0.5, rationale='test')
    signals.ingest(signal)
    decision = PreTradeRiskEngine(registry, states, signals).evaluate('sig', 'paused')
    assert decision.state == 'blocked'
    assert 'account-not-active' in decision.blockers


def test_require_approved_rejects_blocked_decision(tmp_path: Path) -> None:
    registry, states, signals = setup_stack(tmp_path)
    signal = add_signal(signals)
    decision = PreTradeRiskEngine(registry, states, signals).evaluate(signal.signal_id, 'acc-1')
    with pytest.raises(PreTradeRiskError, match='pre-trade risk blocked'):
        PreTradeRiskEngine.require_approved(decision)


def test_b4_advances_exactly_to_b5_without_live_execution() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.533'
    assert readiness['current_item'] == 'B4-pre-trade-risk-engine'
    assert readiness['next_item'] == 'B5-multi-account-allocation-copy-engine'
    assert readiness['trading_live_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
