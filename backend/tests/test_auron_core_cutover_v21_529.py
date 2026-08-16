from pathlib import Path

from app.core.auron_core_cutover_v21_529 import CoreCutoverHarness, require_core_cutover_certified
from app.core.auron_integration_readiness_v21_529 import get_integration_readiness


def test_core_cutover_certifies_all_shared_capabilities_without_external_calls(tmp_path: Path) -> None:
    certification = CoreCutoverHarness(tmp_path).certify()
    require_core_cutover_certified(certification)
    assert certification.state == 'core-cutover-certified'
    assert certification.verified_capabilities == ('core', 'trading', 'instagram-content-manager')
    assert certification.command_input_available is True
    assert certification.persistent_ledger_verified is True
    assert certification.policy_fail_closed_verified is True
    assert certification.simulation_path_verified is True
    assert certification.live_provider_execution_enabled is False
    assert certification.external_calls_made == 0
    assert certification.blockers == ()


def test_cutover_harness_persists_simulation_audit_across_repeated_runs(tmp_path: Path) -> None:
    harness = CoreCutoverHarness(tmp_path)
    first = harness.certify()
    second = harness.certify()
    assert first.state == 'core-cutover-certified'
    assert second.state == 'core-cutover-certified'
    assert first.external_calls_made == second.external_calls_made == 0


def test_a6_advances_to_trading_b1_without_enabling_live_provider_execution() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.529'
    assert readiness['current_phase'] == 'B-trading-vertical'
    assert readiness['current_item'] == 'A6-end-to-end-integration-harness-cutover-certification'
    assert readiness['next_item'] == 'B1-trading-multi-account-registry-and-provider-rule-profiles'
    assert readiness['core_next_gate'] == 'trading-account-registry'
    assert readiness['live_provider_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0


def test_a1_through_a6_gates_are_present() -> None:
    readiness = get_integration_readiness()
    gates = set(readiness['completed_gates'])
    for gate in (
        'canonical-roadmap',
        'capability-contract',
        'persistent-ledger',
        'central-policy-gate',
        'command-centre-integration',
        'e2e-integration-harness',
        'core-cutover-certification',
    ):
        assert gate in gates
