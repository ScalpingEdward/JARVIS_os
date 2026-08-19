import pytest

from app.trading.auron_trading_shadow_canary_adapter_v21_605 import (
    TradingShadowCanaryAdapter,TradingShadowCanaryAdapterError)
from app.core.auron_integration_readiness_v21_605 import get_integration_readiness


def adapter(tmp_path): return TradingShadowCanaryAdapter(tmp_path/'trading-shadow.db')


def test_trade_plan_evaluation_is_local_persistent_and_idempotent(tmp_path):
    a=adapter(tmp_path)
    payload={'symbol':'XAUUSD','side':'buy','entry':2500,'stop_loss':2490,'take_profit':2530,'risk_percent':0.5}
    kw=dict(vertical='trading',provider_id='trading-analysis-shadow',scope='analysis-only',
        action_key='evaluate-trade-plan',payload=payload,idempotency_key='k-1')
    ref=a.execute_canary_action(**kw); assert a.execute_canary_action(**kw)==ref
    result=a.read_result(provider_ref=ref); analysis=a.analysis(ref)
    assert result.state=='completed' and result.external_calls_made==0
    assert analysis['decision']=='shadow-valid' and analysis['risk_reward_ratio']==3.0
    assert analysis['broker_connected'] is False and analysis['live_order_created'] is False
    assert analysis['position_mutated'] is False and analysis['network_calls_made']==0


def test_order_intent_is_simulated_not_submitted(tmp_path):
    a=adapter(tmp_path)
    ref=a.execute_canary_action(vertical='trading',provider_id='trading-analysis-shadow',scope='intent-simulation-only',
        action_key='simulate-order-intent',payload={'symbol':'EURUSD','side':'sell','order_type':'limit','quantity':0.2,'intended_price':1.17},
        idempotency_key='k-2')
    analysis=a.analysis(ref)
    assert analysis['intent_state']=='simulated-not-submitted'
    assert analysis['broker_connected'] is False and analysis['live_order_created'] is False
    assert analysis['position_mutated'] is False and analysis['network_calls_made']==0


def test_live_execution_credentials_and_broker_fields_are_rejected(tmp_path):
    a=adapter(tmp_path)
    base={'symbol':'XAUUSD','side':'buy','entry':2500,'stop_loss':2490,'take_profit':2530,'risk_percent':0.5}
    for field,value in [('api_key','secret'),('broker_credentials',{'x':1}),('place_order',True),('broker_url','https://broker.invalid')]:
        payload={**base,field:value}
        with pytest.raises(TradingShadowCanaryAdapterError):
            a.execute_canary_action(vertical='trading',provider_id='trading-analysis-shadow',scope='analysis-only',
                action_key='evaluate-trade-plan',payload=payload,idempotency_key='bad-'+field)


def test_live_order_and_position_actions_fail_closed(tmp_path):
    a=adapter(tmp_path)
    for action in ('place-order','cancel-order','modify-position','close-position'):
        with pytest.raises(TradingShadowCanaryAdapterError):
            a.execute_canary_action(vertical='trading',provider_id='trading-analysis-shadow',scope='shadow-only',
                action_key=action,payload={'symbol':'EURUSD','side':'buy'},idempotency_key=action)


def test_wrong_provider_and_invalid_plan_fail_closed(tmp_path):
    a=adapter(tmp_path)
    with pytest.raises(TradingShadowCanaryAdapterError):
        a.execute_canary_action(vertical='trading',provider_id='trading-live-provider',scope='analysis-only',
            action_key='evaluate-trade-plan',payload={'symbol':'XAUUSD','side':'buy','entry':1,'stop_loss':0.9,'take_profit':1.2,'risk_percent':1},idempotency_key='x')
    with pytest.raises(TradingShadowCanaryAdapterError):
        a.execute_canary_action(vertical='trading',provider_id='trading-analysis-shadow',scope='analysis-only',
            action_key='evaluate-trade-plan',payload={'symbol':'XAUUSD','side':'flat','entry':1,'stop_loss':0.9,'take_profit':1.2,'risk_percent':1},idempotency_key='y')


def test_stop_is_persistent_and_descriptor_keeps_live_trading_disabled(tmp_path):
    a=adapter(tmp_path); a.stop_canary(activation_id='shadow-a1',reason='operator-stop')
    assert a.is_stopped('shadow-a1') is True
    d=a.descriptor(); r=get_integration_readiness()
    assert d.shadow_only is True and d.broker_credentials_required is False
    assert d.broker_network_enabled is False and d.live_order_placement_enabled is False
    assert d.order_cancel_modify_enabled is False and d.position_mutation_enabled is False
    assert d.production_transport_enabled is False
    assert r['roadmap_version']=='v21.605' and r['next_item']=='G19-trading-shadow-end-to-end-certification'
    assert r['trading_execution_enabled'] is False and r['trading_broker_network_enabled'] is False
