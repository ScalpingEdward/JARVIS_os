import pytest

from app.core.auron_production_readiness_canary_gate_v21_583 import (
    CanaryReadinessEvidence,
    ProductionReadinessCanaryError,
    ProductionReadinessCanaryGate,
)
from app.core.auron_integration_readiness_v21_583 import get_integration_readiness


def evidence(**overrides):
    data = dict(
        vertical='trading', provider_id='mt5-demo',
        e1_governance_certified=True, e2_simulation_certified=True,
        e3_reconciliation_certified=True, provider_health_green=True,
        policy_gate_green=True, kill_switch_available=True, kill_switch_active=True,
        reconciliation_available=True, idempotency_available=True,
        operator_approved=True, canary_scope_explicit=True, max_canary_actions=1,
        transport_configured=True, transport_enabled=False,
        rollback_or_stop_control_available=True,
        observed_at='2026-08-18T17:00:00+00:00',
    )
    data.update(overrides)
    return CanaryReadinessEvidence(**data)


def test_green_evidence_certifies_readiness_without_enabling_transport():
    decision = ProductionReadinessCanaryGate().evaluate(evidence(), at='2026-08-18T17:01:00+00:00')
    assert decision.ready_for_canary_activation is True
    assert decision.blockers == ()
    assert decision.max_canary_actions == 1
    assert decision.live_transport_enabled_by_gate is False
    assert decision.kill_switch_must_remain_available is True


def test_transport_already_enabled_fails_closed():
    decision = ProductionReadinessCanaryGate().evaluate(evidence(transport_enabled=True))
    assert decision.ready_for_canary_activation is False
    assert 'transport-must-remain-disabled-during-E4-certification' in decision.blockers


def test_missing_prior_certification_and_operator_approval_fail_closed():
    decision = ProductionReadinessCanaryGate().evaluate(evidence(
        e3_reconciliation_certified=False, operator_approved=False))
    assert decision.ready_for_canary_activation is False
    assert 'E3-reconciliation-certification-required' in decision.blockers
    assert 'explicit-operator-approval-required' in decision.blockers


def test_canary_scope_is_strictly_bounded():
    gate = ProductionReadinessCanaryGate()
    assert gate.evaluate(evidence(max_canary_actions=0)).ready_for_canary_activation is False
    assert gate.evaluate(evidence(max_canary_actions=6)).ready_for_canary_activation is False


def test_kill_switch_must_be_available_and_active_before_activation():
    decision = ProductionReadinessCanaryGate().evaluate(evidence(kill_switch_active=False))
    assert decision.ready_for_canary_activation is False
    assert 'kill-switch-must-be-active-before-canary-activation' in decision.blockers


def test_require_ready_raises_for_blocked_decision():
    gate = ProductionReadinessCanaryGate()
    with pytest.raises(ProductionReadinessCanaryError):
        gate.require_ready(gate.evaluate(evidence(provider_health_green=False)))


def test_e4_completes_phase_e_without_live_enablement():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.583'
    assert readiness['phase_e_complete'] is True
    assert readiness['next_item'] == 'F1-controlled-provider-canary-activation-contract'
    assert readiness['live_transports_enabled'] is False
    assert readiness['production_canary_auto_activation_enabled'] is False
