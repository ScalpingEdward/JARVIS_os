from pathlib import Path

import pytest

from app.core.auron_capability_adapter_contract_v21_525 import ExecutionContext, ExecutionResult
from app.core.auron_execution_ledger_v21_526 import ExecutionAuditLedger, LedgerInvariantError
from app.core.auron_integration_readiness_v21_526 import get_integration_readiness


def ledger(tmp_path: Path) -> ExecutionAuditLedger:
    return ExecutionAuditLedger(tmp_path / 'auron_execution_ledger.sqlite3')


def test_intent_persists_across_ledger_instances(tmp_path: Path) -> None:
    db = tmp_path / 'ledger.sqlite3'
    first = ExecutionAuditLedger(db)
    context = ExecutionContext(mode='simulation', request_id='req-persist', capability='trading')
    first.record_intent(context, {'symbol': 'XAUUSD', 'side': 'buy'})

    second = ExecutionAuditLedger(db)
    record = second.get('req-persist')
    assert record is not None
    assert record.capability == 'trading'
    assert record.status == 'received'
    assert record.reconciliation_state == 'not-applicable'


def test_same_idempotency_key_same_intent_replays(tmp_path: Path) -> None:
    store = ledger(tmp_path)
    context = ExecutionContext(mode='simulation', request_id='req-1', capability='trading')
    first = store.record_intent(context, {'risk': 0.5})
    second = store.record_intent(context, {'risk': 0.5})
    assert first == second
    assert len(store.list_recent()) == 1


def test_same_idempotency_key_different_intent_fails_closed(tmp_path: Path) -> None:
    store = ledger(tmp_path)
    context = ExecutionContext(mode='simulation', request_id='req-2', capability='trading')
    store.record_intent(context, {'risk': 0.5})
    with pytest.raises(LedgerInvariantError):
        store.record_intent(context, {'risk': 1.0})


def test_simulation_result_is_persisted_without_external_calls(tmp_path: Path) -> None:
    store = ledger(tmp_path)
    context = ExecutionContext(mode='simulation', request_id='req-sim', capability='instagram-content-manager')
    store.record_intent(context, {'draft_id': 'd1'})
    record = store.record_result(
        ExecutionResult(
            request_id='req-sim', capability='instagram-content-manager', mode='simulation',
            status='simulated', external_calls_made=0, detail='dry run',
        )
    )
    assert record.status == 'simulated'
    assert record.external_calls_made == 0
    assert record.reconciliation_state == 'not-applicable'


def test_result_without_intent_is_rejected(tmp_path: Path) -> None:
    store = ledger(tmp_path)
    with pytest.raises(LedgerInvariantError):
        store.record_result(ExecutionResult('missing', 'trading', 'simulation', 'simulated', 0))


def test_live_execution_can_be_reconciled_by_provider_reference(tmp_path: Path) -> None:
    store = ledger(tmp_path)
    context = ExecutionContext(mode='live', request_id='req-live', capability='trading')
    store.record_intent(context, {'symbol': 'EURUSD'})
    executed = store.record_result(
        ExecutionResult(
            request_id='req-live', capability='trading', mode='live', status='executed',
            external_calls_made=1, provider_reference='order-123',
        )
    )
    assert executed.reconciliation_state == 'pending'
    matched = store.reconcile('req-live', 'order-123', detail='provider snapshot')
    assert matched.reconciliation_state == 'matched'
    history = store.reconciliation_history('req-live')
    assert history[-1]['state'] == 'matched'


def test_reconciliation_mismatch_is_observable(tmp_path: Path) -> None:
    store = ledger(tmp_path)
    context = ExecutionContext(mode='live', request_id='req-mismatch', capability='trading')
    store.record_intent(context, {'symbol': 'GBPUSD'})
    store.record_result(
        ExecutionResult('req-mismatch', 'trading', 'live', 'executed', 1, provider_reference='expected')
    )
    record = store.reconcile('req-mismatch', 'different')
    assert record.reconciliation_state == 'mismatched'


def test_simulation_cannot_be_provider_reconciled(tmp_path: Path) -> None:
    store = ledger(tmp_path)
    context = ExecutionContext(mode='simulation', request_id='req-no-reconcile', capability='trading')
    store.record_intent(context, {})
    store.record_result(ExecutionResult('req-no-reconcile', 'trading', 'simulation', 'simulated', 0))
    with pytest.raises(LedgerInvariantError):
        store.reconcile('req-no-reconcile', None)


def test_a3_advances_exactly_to_a4() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.526'
    assert readiness['current_item'] == 'A3-persistent-execution-audit-ledger-idempotency-reconciliation'
    assert readiness['next_item'] == 'A4-central-policy-gate-approval-environment-kill-switch-scopes'
    assert readiness['core_next_gate'] == 'policy-gate'
    assert readiness['persistent_state'] is True
    assert readiness['external_calls_made'] == 0
