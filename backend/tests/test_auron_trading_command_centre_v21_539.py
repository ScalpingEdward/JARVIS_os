from pathlib import Path

from app.core.auron_integration_readiness_v21_539 import get_integration_readiness
from app.trading.auron_controlled_live_enablement_v21_538 import ControlledLiveEnablementService
from app.trading.auron_mt5_broker_adapter_v21_536 import InMemoryReadOnlyBrokerSource, MT5BrokerReadOnlyPaperAdapter
from app.trading.auron_trading_account_state_v21_531 import TradingAccountStateStore, make_manual_snapshot
from app.trading.auron_trading_command_centre_v21_539 import TradingCommandCentreService
from app.trading.auron_trading_reconciliation_canary_v21_537 import TradingReconciliationCanaryService
from app.trading.auron_trading_registry_v21_530 import ProviderRuleProfile, TradingAccount, TradingAccountRegistry


def service(tmp_path: Path):
    r=TradingAccountRegistry(tmp_path/'r.db')
    r.upsert_rule_profile(ProviderRuleProfile('Firm','default',5.0,10.0,8.0,4,None,None,True,False,True,True,False,None,None,''))
    r.register_account(TradingAccount('acc-1','Firm','ref','100K','evaluation','active','USD',100000,'default'))
    s=TradingAccountStateStore(tmp_path/'s.db',r)
    s.upsert_snapshot(make_manual_snapshot(account_id='acc-1',balance=98000,equity=97500,floating_pnl=-500,realized_pnl=-2000,trading_day_start_balance=100000))
    a=MT5BrokerReadOnlyPaperAdapter(tmp_path/'p.db',r,s,InMemoryReadOnlyBrokerSource({}))
    recon=TradingReconciliationCanaryService(tmp_path/'c.db',r,s,a)
    live=ControlledLiveEnablementService(tmp_path/'l.db',r,recon)
    return TradingCommandCentreService(r,s,a,recon,live)


def test_account_view_exposes_dd_headroom_and_alerts(tmp_path):
    svc=service(tmp_path); v=svc.account_view('acc-1')
    assert v['daily_drawdown_used_pct']==2.5
    assert v['daily_drawdown_headroom_pct']==2.5
    assert v['max_drawdown_used_pct']==2.5
    assert v['max_drawdown_headroom_pct']==7.5
    assert 'canary-not-certified' in v['alerts']
    assert v['external_calls_made']==0


def test_snapshot_preserves_command_field_and_no_provider_write(tmp_path):
    snap=service(tmp_path).snapshot()
    assert snap['command_input_available'] is True
    assert snap['provider_write_enabled'] is False
    assert snap['live_execution_default'] is False
    assert snap['external_calls_made']==0


def test_kill_controls_are_exposed_fail_closed(tmp_path):
    svc=service(tmp_path)
    result=svc.set_kill_controls('acc-1',global_kill_switch=True,account_kill_switch=True)
    assert result['scope']['global_kill_switch'] is True
    assert result['scope']['account_kill_switch'] is True
    assert result['scope']['enabled'] is False


def test_b10_completes_phase_b_architecture_without_live_enablement():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.539'
    assert r['phase_b_architecture_complete'] is True
    assert r['trading_live_execution_enabled'] is False
    assert r['next_item']=='C1-instagram-brand-account-registry-content-calendar'
