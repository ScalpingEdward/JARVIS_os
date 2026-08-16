from pathlib import Path
import pytest
from app.core.auron_integration_readiness_v21_536 import get_integration_readiness
from app.trading.auron_mt5_broker_adapter_v21_536 import BrokerAccountSnapshot, BrokerAdapterError, InMemoryReadOnlyBrokerSource, MT5BrokerReadOnlyPaperAdapter
from app.trading.auron_multi_account_allocation_v21_534 import AccountChildIntent
from app.trading.auron_trading_account_state_v21_531 import TradingAccountStateStore, TradingDayState
from app.trading.auron_trading_guards_v21_535 import GuardDecision
from app.trading.auron_trading_registry_v21_530 import ProviderRuleProfile, TradingAccount, TradingAccountRegistry

def stack(tmp_path: Path):
    r=TradingAccountRegistry(tmp_path/'r.sqlite3')
    r.upsert_rule_profile(ProviderRuleProfile('Firm','default',5.0,10.0,8.0,4,None,None,True,False,True,True,False,None,None,''))
    r.register_account(TradingAccount('acc-1','Firm','ref','100K','evaluation','active','USD',100000,'default'))
    s=TradingAccountStateStore(tmp_path/'s.sqlite3',r)
    snap=BrokerAccountSnapshot('acc-1',100000,99500,-500,0,1500,1500,500,99000,(),(),TradingDayState('2026-08-17',0,100000,0,False))
    a=MT5BrokerReadOnlyPaperAdapter(tmp_path/'p.sqlite3',r,s,InMemoryReadOnlyBrokerSource({'acc-1':snap}))
    i=AccountChildIntent('sig:acc-1','sig','acc-1','XAUUSD','buy','market',2400,2380,2420,500,0.5,0.25,'ready-for-guard-evaluation',(),0)
    g=GuardDecision('sig:acc-1','acc-1','ready-for-paper-execution',(),1.5,0.5,0,0)
    return s,a,i,g

def test_read_only_sync(tmp_path):
    s,a,_,_=stack(tmp_path); x=a.sync_read_only('acc-1'); assert x.equity==99500; assert s.get_snapshot('acc-1')==x

def test_paper_execution_is_idempotent(tmp_path):
    _,a,i,g=stack(tmp_path); x=a.paper_execute(i,g); y=a.paper_execute(i,g); assert x==y; assert x.state=='paper-filled'; assert x.external_calls_made==0

def test_blocked_guard_fails(tmp_path):
    _,a,i,_=stack(tmp_path); g=GuardDecision(i.child_intent_id,'acc-1','blocked',('news',),0,0,0,0)
    with pytest.raises(BrokerAdapterError): a.paper_execute(i,g)

def test_no_live_execution_path(tmp_path):
    _,a,_,_=stack(tmp_path); assert a.live_execution_available() is False; assert not hasattr(a,'live_execute')

def test_b7_advances_to_b8():
    x=get_integration_readiness(); assert x['roadmap_version']=='v21.536'; assert x['next_item']=='B8-reconciliation-canary-certification'; assert x['trading_live_execution_enabled'] is False
