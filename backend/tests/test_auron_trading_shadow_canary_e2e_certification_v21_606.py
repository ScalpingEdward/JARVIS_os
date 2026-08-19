from dataclasses import replace
import pytest

from app.trading.auron_trading_shadow_canary_e2e_certification_v21_606 import (
    TradingShadowCanaryE2ECertificationError,TradingShadowCanaryE2ECertificationHarness,TradingShadowCanaryE2ERequest)
from app.core.auron_integration_readiness_v21_606 import get_integration_readiness
from app.core.auron_production_readiness_canary_gate_v21_583 import CanaryReadinessDecision


def ready():
    return CanaryReadinessDecision('d-trading-shadow','trading','trading-analysis-shadow',True,(),1,True,False,
        '2026-08-19T18:00:00+00:00','evidence-trading-shadow')


def request(**overrides):
    values=dict(readiness_decision=ready(),operator_id='operator-1',scope='trade-plan-analysis-only',
        action_key='evaluate-trade-plan',payload={'symbol':'XAUUSD','side':'buy','entry':2500,'stop_loss':2490,
        'take_profit':2530,'risk_percent':0.5})
    values.update(overrides); return TradingShadowCanaryE2ERequest(**values)


def test_full_shadow_chain_certifies_without_live_trading(tmp_path):
    r=TradingShadowCanaryE2ECertificationHarness(tmp_path).run(request())
    assert r.execution_state=='provider-submitted' and r.reconciliation_state=='reconciled'
    assert r.certification_outcome=='promote' and r.certified is True
    assert r.broker_network_enabled is False and r.live_order_placement_enabled is False
    assert r.position_mutation_enabled is False and r.production_transport_enabled is False
    assert r.network_calls_made==0


def test_same_shadow_request_is_idempotent(tmp_path):
    h=TradingShadowCanaryE2ECertificationHarness(tmp_path); a=h.run(request()); b=h.run(request())
    assert a.activation_id==b.activation_id and a.execution_id==b.execution_id
    assert a.reconciliation_id==b.reconciliation_id and a.certification_id==b.certification_id


def test_wrong_provider_and_live_action_fail_before_execution(tmp_path):
    h=TradingShadowCanaryE2ECertificationHarness(tmp_path/'a')
    with pytest.raises(TradingShadowCanaryE2ECertificationError):
        h.run(request(readiness_decision=replace(ready(),provider_id='trading-live-provider')))
    with pytest.raises(TradingShadowCanaryE2ECertificationError):
        TradingShadowCanaryE2ECertificationHarness(tmp_path/'b').run(request(action_key='place-order'))


def test_simulated_order_intent_certifies_but_is_never_submitted_live(tmp_path):
    h=TradingShadowCanaryE2ECertificationHarness(tmp_path)
    r=h.run(request(action_key='simulate-order-intent',scope='order-intent-simulation-only',
        payload={'symbol':'XAUUSD','side':'buy','order_type':'limit','quantity':0.1,'intended_price':2498}))
    assert r.certified is True and r.live_order_placement_enabled is False and r.network_calls_made==0


def test_health_or_operator_approval_drift_yields_hold(tmp_path):
    a=TradingShadowCanaryE2ECertificationHarness(tmp_path/'a').run(request(provider_health_green=False))
    b=TradingShadowCanaryE2ECertificationHarness(tmp_path/'b').run(request(operator_promotion_approved=False))
    assert a.certification_outcome=='hold' and a.certified is False
    assert b.certification_outcome=='hold' and b.certified is False


def test_g19_readiness_advances_to_g20_without_enabling_live_trading():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.606'
    assert r['next_item']=='G20-trading-shadow-health-drift-command-centre-certification'
    assert r['trading_execution_enabled'] is False and r['trading_broker_network_enabled'] is False
    assert r['trading_position_mutation_enabled'] is False and r['live_transports_enabled'] is False
