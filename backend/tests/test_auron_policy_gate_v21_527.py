import pytest

from app.core.auron_capability_adapter_contract_v21_525 import ExecutionContext
from app.core.auron_integration_readiness_v21_527 import get_integration_readiness
from app.core.auron_policy_gate_v21_527 import CentralPolicyGate, PolicyGateError, PolicyState


def test_default_policy_fails_closed_for_live() -> None:
    gate = CentralPolicyGate()
    context = ExecutionContext(mode='live', request_id='live-1', capability='trading', operator_approved=True, external_execution_allowed=True)
    decision = gate.evaluate(context, required_scope='external.execute')
    assert decision.allowed is False
    assert 'environment-not-production' in decision.blockers
    assert 'global-kill-switch-active' in decision.blockers
    assert 'capability-kill-switch-active' in decision.blockers
    assert decision.external_calls_made == 0


def test_simulation_requires_explicit_capability_scope() -> None:
    gate = CentralPolicyGate(PolicyState(enabled_scopes={'trading': ('simulate',)}))
    context = ExecutionContext(mode='simulation', request_id='sim-1', capability='trading')
    decision = gate.evaluate(context, required_scope='simulate')
    assert decision.allowed is True
    assert decision.external_execution_allowed is False


def test_simulation_missing_scope_is_blocked() -> None:
    gate = CentralPolicyGate(PolicyState(enabled_scopes={'trading': ()}))
    decision = gate.evaluate(ExecutionContext(mode='simulation', request_id='sim-2', capability='trading'), required_scope='simulate')
    assert decision.allowed is False
    assert 'capability-scope-missing' in decision.blockers


def test_live_requires_every_gate() -> None:
    state = PolicyState(
        environment='production',
        global_kill_switch=False,
        capability_kill_switches={'trading': False},
        enabled_scopes={'trading': ('external.execute',)},
        live_capabilities=('trading',),
    )
    gate = CentralPolicyGate(state)
    context = ExecutionContext(mode='live', request_id='live-ok', capability='trading', operator_approved=True, external_execution_allowed=True)
    decision = gate.require(context, required_scope='external.execute')
    assert decision.allowed is True
    assert decision.external_execution_allowed is True
    assert decision.external_calls_made == 0


def test_operator_approval_is_mandatory_for_live() -> None:
    state = PolicyState(environment='production', global_kill_switch=False, capability_kill_switches={'trading': False}, enabled_scopes={'trading': ('external.execute',)}, live_capabilities=('trading',))
    gate = CentralPolicyGate(state)
    context = ExecutionContext(mode='live', request_id='live-no-approval', capability='trading', operator_approved=False, external_execution_allowed=True)
    with pytest.raises(PolicyGateError, match='operator-approval-missing'):
        gate.require(context, required_scope='external.execute')


def test_global_kill_switch_overrides_other_live_permissions() -> None:
    state = PolicyState(environment='production', global_kill_switch=True, capability_kill_switches={'trading': False}, enabled_scopes={'trading': ('external.execute',)}, live_capabilities=('trading',))
    gate = CentralPolicyGate(state)
    decision = gate.evaluate(ExecutionContext(mode='live', request_id='kill', capability='trading', operator_approved=True, external_execution_allowed=True), required_scope='external.execute')
    assert decision.allowed is False
    assert 'global-kill-switch-active' in decision.blockers


def test_capability_kill_switch_defaults_to_blocked() -> None:
    state = PolicyState(environment='production', global_kill_switch=False, enabled_scopes={'instagram-content-manager': ('external.execute',)}, live_capabilities=('instagram-content-manager',))
    gate = CentralPolicyGate(state)
    decision = gate.evaluate(ExecutionContext(mode='live', request_id='content', capability='instagram-content-manager', operator_approved=True, external_execution_allowed=True), required_scope='external.execute')
    assert 'capability-kill-switch-active' in decision.blockers


def test_a4_advances_exactly_to_a5() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.527'
    assert readiness['current_item'] == 'A4-central-policy-gate-approval-environment-kill-switch-scopes'
    assert readiness['next_item'] == 'A5-command-centre-real-backend-state-actions-errors-approvals-audit'
    assert readiness['core_next_gate'] == 'command-centre-integration'
    assert readiness['policy_snapshot']['policy']['global_kill_switch'] is True
    assert readiness['external_calls_made'] == 0
