from app.core.auron_trading_shadow_canary_selection_v21_604 import TradingShadowCanarySelectionPolicyV21_604
from app.core.auron_integration_readiness_v21_604 import get_integration_readiness


def test_g17_selects_shadow_only_trading_candidate():
    d=TradingShadowCanarySelectionPolicyV21_604().select()
    assert d.selected_vertical=='trading'
    assert d.provider_id=='trading-analysis-shadow'
    assert d.adapter_id=='trading-shadow-canary-v1'
    assert d.shadow_only is True
    assert d.allowed_actions==('evaluate-trade-plan','simulate-order-intent')


def test_live_order_broker_and_position_mutation_are_disabled():
    d=TradingShadowCanarySelectionPolicyV21_604().select()
    assert d.live_order_placement_enabled is False
    assert d.broker_network_enabled is False
    assert d.position_mutation_enabled is False
    assert d.production_transport_enabled is False


def test_live_provider_is_ineligible_by_policy():
    p=TradingShadowCanarySelectionPolicyV21_604()
    live=next(c for c in p.candidates() if c.provider_id=='trading-live-provider')
    assert live.side_effect_free is False
    assert live.broker_network_required is True
    assert live.order_placement_capable is True
    assert live.position_mutation_capable is True
    assert 'place-order' in live.allowed_actions
    selected=p.select()
    assert selected.provider_id != live.provider_id


def test_only_analysis_and_simulation_actions_are_selected():
    d=TradingShadowCanarySelectionPolicyV21_604().select()
    forbidden={'place-order','cancel-order','modify-position','close-position'}
    assert forbidden.isdisjoint(d.allowed_actions)


def test_g17_readiness_advances_to_g18_without_enabling_trading():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.604'
    assert r['next_item']=='G18-trading-shadow-canary-adapter'
    assert r['trading_execution_enabled'] is False
    assert r['trading_broker_network_enabled'] is False
    assert r['trading_position_mutation_enabled'] is False
    assert r['live_transports_enabled'] is False
