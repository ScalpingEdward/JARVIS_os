from dataclasses import replace
import pytest

from app.core.auron_controlled_provider_canary_contract_v21_584 import CanaryActivationRequest, ControlledProviderCanaryContract, ControlledProviderCanaryError
from app.core.auron_production_readiness_canary_gate_v21_583 import CanaryReadinessDecision
from app.core.auron_integration_readiness_v21_584 import get_integration_readiness


def ready():
    return CanaryReadinessDecision('d1','research','provider-a',True,(),3,True,False,'2026-08-18T17:00:00+00:00','evidence')


def request(**overrides):
    values=dict(readiness_decision=ready(),operator_id='operator-1',requested_actions=2,scope='read-only-canary',kill_switch_active=True,reconciliation_ready=True,stop_control_ready=True,transport_enabled_before_request=False)
    values.update(overrides); return CanaryActivationRequest(**values)


def test_green_request_produces_stable_authorization_without_transport():
    c=ControlledProviderCanaryContract(); a=c.evaluate(request()); b=c.evaluate(request())
    assert a.activation_authorized is True and a.activation_id==b.activation_id
    assert a.action_allowance==2 and a.live_transport_enabled_by_contract is False


def test_request_cannot_exceed_e4_bound():
    d=ControlledProviderCanaryContract().evaluate(request(requested_actions=4))
    assert d.activation_authorized is False and 'requested-actions-exceed-E4-bound' in d.blockers


def test_kill_reconciliation_and_stop_are_mandatory():
    d=ControlledProviderCanaryContract().evaluate(request(kill_switch_active=False,reconciliation_ready=False,stop_control_ready=False))
    assert d.activation_authorized is False
    assert {'kill-switch-must-be-active','reconciliation-must-be-ready','stop-control-must-be-ready'} <= set(d.blockers)


def test_transport_must_not_already_be_live():
    d=ControlledProviderCanaryContract().evaluate(request(transport_enabled_before_request=True))
    assert d.activation_authorized is False and d.live_transport_enabled_by_contract is False


def test_failed_e4_decision_is_rejected():
    bad=replace(ready(),ready_for_canary_activation=False,blockers=('x',))
    c=ControlledProviderCanaryContract(); d=c.evaluate(request(readiness_decision=bad))
    with pytest.raises(ControlledProviderCanaryError): c.require_authorized(d)


def test_f1_readiness_advances_to_execution_boundary():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.584'
    assert r['next_item']=='F2-controlled-canary-execution-boundary'
    assert r['live_transports_enabled'] is False
