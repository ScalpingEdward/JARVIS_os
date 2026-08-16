from pathlib import Path

from app.core.auron_integration_readiness_v21_537 import get_integration_readiness
from app.trading.auron_mt5_broker_adapter_v21_536 import (
    BrokerAccountSnapshot,
    InMemoryReadOnlyBrokerSource,
    MT5BrokerReadOnlyPaperAdapter,
)
from app.trading.auron_multi_account_allocation_v21_534 import AccountChildIntent
from app.trading.auron_trading_account_state_v21_531 import TradingAccountStateStore, TradingDayState
from app.trading.auron_trading_guards_v21_535 import GuardDecision
from app.trading.auron_trading_reconciliation_canary_v21_537 import TradingReconciliationCanaryService
from app.trading.auron_trading_registry_v21_530 import ProviderRuleProfile, TradingAccount, TradingAccountRegistry


def stack(tmp_path: Path, required_matches: int = 3):
    registry = TradingAccountRegistry(tmp_path / 'registry.sqlite3')
    registry.upsert_rule_profile(ProviderRuleProfile('Firm','default',5.0,10.0,8.0,4,None,None,True,False,True,True,False,None,None,''))
    registry.register_account(TradingAccount('acc-1','Firm','ref','100K','evaluation','active','USD',100000,'default'))
    states = TradingAccountStateStore(tmp_path / 'state.sqlite3', registry)
    snapshot = BrokerAccountSnapshot(
        'acc-1',100000,99750,-250,0,1250,1250,500,99250,(),(),
        TradingDayState('2026-08-17',0,100000,0,False),'mt5-read-only-test'
    )
    adapter = MT5BrokerReadOnlyPaperAdapter(
        tmp_path / 'paper.sqlite3', registry, states,
        InMemoryReadOnlyBrokerSource({'acc-1': snapshot}),
    )
    adapter.sync_read_only('acc-1')
    service = TradingReconciliationCanaryService(
        tmp_path / 'recon.sqlite3', registry, states, adapter, required_matches=required_matches,
    )
    return registry, states, adapter, service


def intent(index: int) -> AccountChildIntent:
    return AccountChildIntent(
        f'sig-{index}:acc-1', f'sig-{index}', 'acc-1', 'XAUUSD', 'buy', 'market',
        2400.0, 2380.0, 2420.0, 500.0, 0.5, 0.25,
        'ready-for-guard-evaluation', (), 0,
    )


def guard(child: AccountChildIntent) -> GuardDecision:
    return GuardDecision(child.child_intent_id, child.account_id, 'ready-for-paper-execution', (), 1.25, 0.25, 0, 0)


def test_matching_paper_execution_reconciles_and_persists(tmp_path: Path) -> None:
    _, _, adapter, service = stack(tmp_path, required_matches=1)
    child = intent(1)
    adapter.paper_execute(child, guard(child))
    first = service.reconcile(child)
    second = service.reconcile(child)
    assert first == second
    assert first.state == 'matched'
    assert first.blockers == ()
    assert 'paper-integrity-matched' in first.checks
    assert first.observed_state_source == 'mt5-read-only-test'
    assert first.external_calls_made == 0


def test_missing_paper_execution_fails_reconciliation_closed(tmp_path: Path) -> None:
    _, _, _, service = stack(tmp_path, required_matches=1)
    result = service.reconcile(intent(2))
    assert result.state == 'mismatched'
    assert 'paper-execution-missing' in result.blockers


def test_canary_requires_configured_number_of_clean_matches(tmp_path: Path) -> None:
    _, _, adapter, service = stack(tmp_path, required_matches=3)
    for index in (1, 2):
        child = intent(index)
        adapter.paper_execute(child, guard(child))
        service.reconcile(child)
    early = service.certify_canary('acc-1')
    assert early.state == 'not-certified'
    assert 'insufficient-matched-reconciliations' in early.blockers
    assert early.live_execution_enabled is False

    child = intent(3)
    adapter.paper_execute(child, guard(child))
    service.reconcile(child)
    certified = service.certify_canary('acc-1')
    assert certified.state == 'canary-certified'
    assert certified.matched_reconciliations == 3
    assert certified.blockers == ()
    assert certified.live_execution_enabled is False
    assert certified.external_calls_made == 0


def test_any_reconciliation_mismatch_blocks_canary(tmp_path: Path) -> None:
    _, _, adapter, service = stack(tmp_path, required_matches=1)
    good = intent(1)
    adapter.paper_execute(good, guard(good))
    service.reconcile(good)
    service.reconcile(intent(99))
    certificate = service.certify_canary('acc-1')
    assert certificate.state == 'not-certified'
    assert 'reconciliation-mismatches-present' in certificate.blockers
    assert certificate.live_execution_enabled is False


def test_b8_advances_exactly_to_b9_without_live_enablement() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.537'
    assert readiness['current_item'] == 'B8-reconciliation-canary-certification'
    assert readiness['next_item'] == 'B9-controlled-multi-account-live-enablement'
    assert readiness['trading_live_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
