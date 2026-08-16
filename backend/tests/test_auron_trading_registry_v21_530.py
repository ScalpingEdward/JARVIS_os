from pathlib import Path

import pytest

from app.core.auron_integration_readiness_v21_530 import get_integration_readiness
from app.trading.auron_trading_registry_v21_530 import (
    ProviderRuleProfile,
    TradingAccount,
    TradingAccountRegistry,
    TradingRegistryError,
    reference_prop_profiles,
)


def registry(tmp_path: Path) -> TradingAccountRegistry:
    return TradingAccountRegistry(tmp_path / 'trading_registry.sqlite3')


def test_rule_profiles_persist_and_reload(tmp_path: Path) -> None:
    store = registry(tmp_path)
    profile = ProviderRuleProfile('TestFirm', '100k', 5.0, 10.0, 8.0, 4, 120, 5, True, False, True, True, False, None, None, 'test')
    store.upsert_rule_profile(profile)
    reopened = TradingAccountRegistry(tmp_path / 'trading_registry.sqlite3')
    assert reopened.get_rule_profile('TestFirm', '100k') == profile


def test_account_requires_existing_rule_profile(tmp_path: Path) -> None:
    store = registry(tmp_path)
    account = TradingAccount('acc-1','MissingFirm','123','Primary','evaluation','active','USD',100000,'default')
    with pytest.raises(TradingRegistryError, match='rule profile'):
        store.register_account(account)


def test_multi_account_same_provider_is_supported(tmp_path: Path) -> None:
    store = registry(tmp_path)
    store.upsert_rule_profile(ProviderRuleProfile('Firm','default',5,10,8,4,None,None,True,False,True,True,False,None,None,''))
    store.register_account(TradingAccount('a1','Firm','ref-1','100K-A','evaluation','active','USD',100000,'default'))
    store.register_account(TradingAccount('a2','Firm','ref-2','100K-B','funded','paused','USD',100000,'default'))
    accounts = store.list_accounts('Firm')
    assert {a.account_id for a in accounts} == {'a1','a2'}


def test_duplicate_provider_reference_is_rejected(tmp_path: Path) -> None:
    store = registry(tmp_path)
    store.upsert_rule_profile(ProviderRuleProfile('Firm','default',None,None,None,None,None,None,True,True,True,True,False,None,None,''))
    store.register_account(TradingAccount('a1','Firm','same','A','paper','active','USD',10000,'default'))
    with pytest.raises(TradingRegistryError):
        store.register_account(TradingAccount('a2','Firm','same','B','paper','active','USD',10000,'default'))


def test_reference_profiles_remain_non_live_configuration() -> None:
    profiles = reference_prop_profiles()
    assert {p.provider for p in profiles} >= {'The5ers','FundedNext','E8','FXIFY','SimFi'}
    assert all(p.cross_account_hedging_allowed is False for p in profiles)


def test_b1_advances_exactly_to_b2() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.530'
    assert readiness['current_phase'] == 'B-trading-vertical'
    assert readiness['current_item'] == 'B1-trading-multi-account-registry-and-provider-rule-profiles'
    assert readiness['next_item'] == 'B2-normalized-trading-account-state'
    assert readiness['trading_live_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
