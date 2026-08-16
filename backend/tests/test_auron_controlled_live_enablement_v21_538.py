from pathlib import Path

from app.core.auron_integration_readiness_v21_538 import get_integration_readiness
from app.trading.auron_controlled_live_enablement_v21_538 import ControlledLiveEnablementService
from app.trading.auron_mt5_broker_adapter_v21_536 import BrokerAccountSnapshot, InMemoryReadOnlyBrokerSource, MT5BrokerReadOnlyPaperAdapter
from app.trading.auron_multi_account_allocation_v21_534 import AccountChildIntent
from app.trading.auron_trading_account_state_v21_531 import TradingAccountStateStore, TradingDayState
from app.trading.auron_trading_guards_v21_535 import GuardDecision
from app.trading.auron_trading_reconciliation_canary_v21_537 import TradingReconciliationCanaryService
from app.trading.auron_trading_registry_v21_530 import ProviderRuleProfile, TradingAccount, TradingAccountRegistry


def stack(tmp_path: Path):
    r = TradingAccountRegistry(tmp_path/'r.sqlite3')
    r.upsert_rule_profile(ProviderRuleProfile('Firm','default',5.0,10.0,8.0,4,None,None,True,False,True,True,False,None,None,''))
    r.register_account(TradingAccount('acc-1','Firm','ref','100K','evaluation','active','USD',100000,'default'))
    s = TradingAccountStateStore(tmp_path/'s.sqlite3', r)
    snap = BrokerAccountSnapshot('acc-1',100000,100000,0,0,0,0,0,100000,(),(),TradingDayState('2026-08-16',0,100000,0,False))
    a = MT5BrokerReadOnlyPaperAdapter(tmp_path/'p.sqlite3',r,s,InMemoryReadOnlyBrokerSource({'acc-1':snap}))
    a.sync_read_only('acc-1')
    i = AccountChildIntent('sig:acc-1','sig','acc-1','XAUUSD','buy','market',2400,2380,2420,500,0.5,0.25,'ready-for-guard-evaluation',(),0)
    g = GuardDecision('sig:acc-1','acc-1','ready-for-paper-execution',(),0,0,0,0)
    a.paper_execute(i,g)
    recon = TradingReconciliationCanaryService(tmp_path/'c.sqlite3',r,s,a,required_matches=1)
    assert recon.reconcile(i).state == 'matched'
    assert recon.certify_canary('acc-1').state == 'canary-certified'
    live = ControlledLiveEnablementService(tmp_path/'l.sqlite3',r,recon)
    return live,i,g


def test_defaults_fail_closed(tmp_path):
    live,i,g = stack(tmp_path)
    d = live.evaluate(i,g)
    assert d.state == 'blocked'
    assert 'live-scope-missing' in d.blockers
    assert d.external_calls_made == 0


def test_kill_switch_and_operator_approval_required(tmp_path):
    live,i,g = stack(tmp_path)
    live.configure_scope('acc-1','Firm',enabled=True,operator_approved=False,global_kill_switch=True,account_kill_switch=True)
    d = live.evaluate(i,g)
    assert d.state == 'blocked'
    assert {'operator-approval-required','global-kill-switch-active','account-kill-switch-active'} <= set(d.blockers)


def test_ready_scope_still_has_disabled_provider_write_boundary(tmp_path):
    live,i,g = stack(tmp_path)
    live.configure_scope('acc-1','Firm',enabled=True,operator_approved=True,global_kill_switch=False,account_kill_switch=False)
    assert live.evaluate(i,g).state == 'ready-for-controlled-live'
    result = live.execute_controlled(i,g)
    # Existing decision is idempotently reused and the default writer cannot reach a broker.
    assert result.state in {'provider-write-disabled','ready-for-controlled-live'}
    assert result.external_calls_made == 0


def test_readiness_remains_live_disabled():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.538'
    assert readiness['trading_live_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
