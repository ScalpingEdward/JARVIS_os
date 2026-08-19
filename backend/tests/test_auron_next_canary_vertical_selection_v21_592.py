from app.core.auron_next_canary_vertical_selection_v21_592 import NextCanaryVerticalSelectionPolicy
from app.core.auron_integration_readiness_v21_592 import get_integration_readiness


def test_instagram_draft_preview_is_selected_as_second_canary():
    decision=NextCanaryVerticalSelectionPolicy().select()
    assert decision.selected_vertical=='instagram-content'
    assert decision.provider_id=='instagram-local-draft-preview'
    assert decision.adapter_id=='instagram-draft-preview-canary-v1'
    assert decision.allowed_actions==('render-draft-preview','inspect-draft-metadata')


def test_selection_does_not_enable_publish_or_trading():
    decision=NextCanaryVerticalSelectionPolicy().select()
    assert decision.production_transport_enabled is False
    assert decision.publish_enabled is False
    assert decision.trading_execution_enabled is False


def test_trading_candidate_is_explicitly_high_consequence_and_ineligible():
    candidates=NextCanaryVerticalSelectionPolicy().candidates()
    trading=next(c for c in candidates if c.vertical=='trading')
    assert trading.side_effect_free is False
    assert trading.write_capable is True
    assert trading.external_network_required is True
    assert trading.risk_score==100


def test_all_eligible_candidates_are_side_effect_free_local_readonly():
    candidates=NextCanaryVerticalSelectionPolicy().candidates()
    eligible=[c for c in candidates if c.side_effect_free and not c.write_capable and not c.external_network_required]
    assert eligible
    assert all(not c.write_capable and not c.external_network_required for c in eligible)


def test_g5_readiness_advances_to_instagram_adapter():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.592'
    assert r['next_item']=='G6-instagram-draft-preview-canary-adapter'
    assert r['instagram_publish_enabled'] is False
    assert r['trading_execution_enabled'] is False
