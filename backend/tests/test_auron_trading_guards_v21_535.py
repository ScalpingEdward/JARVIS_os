from datetime import datetime, timezone
from pathlib import Path

from app.core.auron_integration_readiness_v21_535 import get_integration_readiness
from app.trading.auron_multi_account_allocation_v21_534 import AccountChildIntent
from app.trading.auron_trading_account_state_v21_531 import TradingAccountStateStore, make_manual_snapshot
from app.trading.auron_trading_guards_v21_535 import GuardContext, TradingGuardEngine, TradingGuardPolicy
from app.trading.auron_trading_registry_v21_530 import ProviderRuleProfile, TradingAccount, TradingAccountRegistry


def setup_stack(tmp_path: Path):
    registry = TradingAccountRegistry(tmp_path / 'registry.sqlite3')
    registry.upsert_rule_profile(ProviderRuleProfile('Firm','default',5.0,10.0,8.0,4,None,None,True,False,True,True,False,None,None,''))
    registry.register_account(TradingAccount('acc-1','Firm','ref','100K','evaluation','active','USD',100000,'default'))
    states = TradingAccountStateStore(tmp_path / 'state.sqlite3', registry)
    states.upsert_snapshot(make_manual_snapshot(account_id='acc-1', balance=100000, equity=100000, floating_pnl=0, realized_pnl=0))
    intent = AccountChildIntent('sig:acc-1','sig','acc-1','XAUUSD','buy','market',2400,2380,2420,500,0.5,0.25,'ready-for-guard-evaluation',(),0)
    return registry, states, intent


def open_policy(**overrides):
    values = dict(global_kill_switch=False, account_kill_switches={'acc-1': False}, allowed_symbols=('XAUUSD',), session_start_hour_utc=0, session_end_hour_utc=24, max_gross_exposure_pct=5.0, max_open_positions=10, max_daily_loss_pct=4.0)
    values.update(overrides)
    return TradingGuardPolicy(**values)


def monday_noon():
    return GuardContext(datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc))


def test_default_guard_fails_closed_with_kill_switches(tmp_path: Path) -> None:
    registry, states, intent = setup_stack(tmp_path)
    decision = TradingGuardEngine(registry, states).evaluate(intent, monday_noon())
    assert decision.state == 'blocked'
    assert 'global-trading-kill-switch-active' in decision.blockers
    assert 'account-trading-kill-switch-active' in decision.blockers
    assert decision.external_calls_made == 0


def test_healthy_child_intent_can_reach_paper_execution_only(tmp_path: Path) -> None:
    registry, states, intent = setup_stack(tmp_path)
    decision = TradingGuardEngine(registry, states, open_policy()).evaluate(intent, monday_noon())
    assert decision.state == 'ready-for-paper-execution'
    assert decision.blockers == ()
    assert decision.external_calls_made == 0


def test_restricted_news_blocks_trade(tmp_path: Path) -> None:
    registry, states, intent = setup_stack(tmp_path)
    context = GuardContext(datetime(2026,8,17,12,0,tzinfo=timezone.utc), restricted_news_active=True, news_reference='CPI')
    decision = TradingGuardEngine(registry, states, open_policy()).evaluate(intent, context)
    assert decision.state == 'blocked'
    assert 'restricted-news-window-active' in decision.blockers


def test_symbol_and_session_guards_block(tmp_path: Path) -> None:
    registry, states, intent = setup_stack(tmp_path)
    policy = open_policy(allowed_symbols=('EURUSD',), session_start_hour_utc=7, session_end_hour_utc=11)
    decision = TradingGuardEngine(registry, states, policy).evaluate(intent, monday_noon())
    assert 'symbol-not-allowed' in decision.blockers
    assert 'outside-trading-session' in decision.blockers


def test_daily_loss_limit_blocks(tmp_path: Path) -> None:
    registry, states, intent = setup_stack(tmp_path)
    states.upsert_snapshot(make_manual_snapshot(account_id='acc-1', balance=96000, equity=96000, floating_pnl=0, realized_pnl=-4000, trading_day_start_balance=100000))
    decision = TradingGuardEngine(registry, states, open_policy(max_daily_loss_pct=4.0)).evaluate(intent, monday_noon())
    assert decision.state == 'blocked'
    assert 'daily-loss-limit-reached' in decision.blockers


def test_per_account_kill_switch_blocks_even_when_global_is_open(tmp_path: Path) -> None:
    registry, states, intent = setup_stack(tmp_path)
    policy = open_policy(account_kill_switches={'acc-1': True})
    decision = TradingGuardEngine(registry, states, policy).evaluate(intent, monday_noon())
    assert decision.state == 'blocked'
    assert 'account-trading-kill-switch-active' in decision.blockers


def test_b6_advances_exactly_to_b7() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.535'
    assert readiness['current_item'] == 'B6-account-session-news-guards-exposure-loss-kill-switches'
    assert readiness['next_item'] == 'B7-mt5-broker-adapter-read-only-paper'
    assert readiness['trading_live_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
