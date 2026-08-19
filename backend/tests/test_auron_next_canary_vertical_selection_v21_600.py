from app.core.auron_next_canary_vertical_selection_v21_600 import NextCanaryVerticalSelectionPolicyV21_600
from app.core.auron_integration_readiness_v21_600 import get_integration_readiness


def test_communications_is_selected_after_three_completed_canaries():
    d=NextCanaryVerticalSelectionPolicyV21_600().select()
    assert d.selected_vertical=='communications'
    assert d.provider_id=='communications-local-draft'
    assert d.adapter_id=='communications-draft-canary-v1'
    assert d.allowed_actions==('render-message-preview','inspect-recipient-plan')


def test_completed_provider_canaries_are_excluded():
    candidates=NextCanaryVerticalSelectionPolicyV21_600().candidates()
    done={c.vertical for c in candidates if c.already_certified}
    assert {'research','instagram-content','files-documents'} <= done


def test_selection_keeps_outbound_and_trading_disabled():
    d=NextCanaryVerticalSelectionPolicyV21_600().select()
    assert d.production_transport_enabled is False
    assert d.provider_write_enabled is False
    assert d.outbound_message_enabled is False
    assert d.trading_execution_enabled is False


def test_live_trading_remains_ineligible():
    candidates=NextCanaryVerticalSelectionPolicyV21_600().candidates()
    live=next(c for c in candidates if c.provider_id=='trading-live-provider')
    assert live.side_effect_free is False
    assert live.write_capable is True
    assert live.external_network_required is True
    assert live.risk_score==100


def test_trading_shadow_is_safe_but_deferred_by_conservative_risk_order():
    policy=NextCanaryVerticalSelectionPolicyV21_600(); candidates=policy.candidates()
    shadow=next(c for c in candidates if c.provider_id=='trading-analysis-shadow')
    communications=next(c for c in candidates if c.vertical=='communications')
    assert shadow.side_effect_free is True and shadow.write_capable is False and shadow.external_network_required is False
    assert communications.risk_score < shadow.risk_score
    assert policy.select().selected_vertical=='communications'


def test_g13_readiness_advances_to_communications_adapter():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.600'
    assert r['next_item']=='G14-communications-draft-canary-adapter'
    assert r['communications_outbound_send_enabled'] is False
    assert r['trading_execution_enabled'] is False
