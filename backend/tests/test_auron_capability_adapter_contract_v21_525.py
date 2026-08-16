import pytest

from app.core.auron_capability_adapter_contract_v21_525 import (
    AdapterHealth,
    AdapterReadiness,
    CapabilityContractError,
    CapabilityDescriptor,
    ContractOnlyAdapter,
    ExecutionContext,
    ExecutionResult,
    assert_result_accounting,
    guard_execution,
    validate_adapter_contract,
)
from app.core.auron_integration_readiness_v21_525 import get_integration_readiness


def test_reference_adapter_contract_is_valid_and_dry() -> None:
    adapter = ContractOnlyAdapter('trading')
    snapshot = validate_adapter_contract(adapter)
    assert snapshot['contract_valid'] is True
    assert snapshot['descriptor']['supported_modes'] == ('simulation',)
    assert snapshot['readiness']['external_execution_enabled'] is False
    assert snapshot['external_calls_made'] == 0


def test_simulation_executes_without_external_calls() -> None:
    adapter = ContractOnlyAdapter('instagram-content-manager')
    result = adapter.execute(
        ExecutionContext(mode='simulation', request_id='req-1', capability='instagram-content-manager'),
        {'draft_id': 'draft-1'},
    )
    assert result.status == 'simulated'
    assert result.external_calls_made == 0


def test_live_execution_fails_closed_for_contract_only_adapter() -> None:
    adapter = ContractOnlyAdapter('trading')
    context = ExecutionContext(
        mode='live', request_id='req-live', capability='trading',
        operator_approved=True, external_execution_allowed=True,
    )
    with pytest.raises(CapabilityContractError):
        guard_execution(adapter, context)


def test_capability_mismatch_fails_closed() -> None:
    adapter = ContractOnlyAdapter('trading')
    with pytest.raises(CapabilityContractError):
        guard_execution(adapter, ExecutionContext(mode='simulation', request_id='x', capability='other'))


def test_invalid_live_readiness_contract_is_rejected() -> None:
    class InvalidAdapter:
        def descriptor(self):
            return CapabilityDescriptor('trading', 'invalid', 'x', ('simulation', 'live'), ('read', 'simulate'))
        def health(self):
            return AdapterHealth('healthy', 'test')
        def readiness(self):
            return AdapterReadiness('integration-ready', (), True)
        def execute(self, context, payload):
            raise AssertionError('must not execute')

    with pytest.raises(CapabilityContractError):
        validate_adapter_contract(InvalidAdapter())


def test_simulated_result_cannot_claim_external_calls() -> None:
    result = ExecutionResult('r', 'trading', 'simulation', 'simulated', 1)
    with pytest.raises(CapabilityContractError):
        assert_result_accounting(result)


def test_a2_advances_exactly_to_a3() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.525'
    assert readiness['current_item'] == 'A2-unified-capability-adapter-contract'
    assert readiness['next_item'] == 'A3-persistent-execution-audit-ledger-idempotency-reconciliation'
    assert readiness['core_next_gate'] == 'persistent-ledger'
    assert readiness['external_calls_made'] == 0
