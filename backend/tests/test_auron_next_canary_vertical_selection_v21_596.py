from app.core.auron_next_canary_vertical_selection_v21_596 import NextCanaryVerticalSelectionPolicyV21_596
from app.core.auron_integration_readiness_v21_596 import get_integration_readiness


def test_files_documents_is_selected_as_third_provider_specific_canary():
    d=NextCanaryVerticalSelectionPolicyV21_596().select()
    assert d.selected_vertical=='files-documents'
    assert d.provider_id=='documents-local-readonly'
    assert d.adapter_id=='documents-readonly-canary-v1'
    assert d.allowed_actions==('inspect-file-metadata','preview-file-version')


def test_already_certified_verticals_are_excluded():
    candidates=NextCanaryVerticalSelectionPolicyV21_596().candidates()
    done={c.vertical for c in candidates if c.already_certified}
    assert {'research','instagram-content'} <= done


def test_live_trading_is_still_ineligible():
    candidates=NextCanaryVerticalSelectionPolicyV21_596().candidates()
    live=next(c for c in candidates if c.provider_id=='trading-live-provider')
    assert live.side_effect_free is False
    assert live.write_capable is True
    assert live.external_network_required is True


def test_selection_keeps_all_external_mutation_disabled():
    d=NextCanaryVerticalSelectionPolicyV21_596().select()
    assert d.production_transport_enabled is False
    assert d.provider_write_enabled is False
    assert d.trading_execution_enabled is False


def test_g9_readiness_advances_to_documents_adapter():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.596'
    assert r['next_item']=='G10-documents-readonly-canary-adapter'
    assert r['documents_provider_write_enabled'] is False
    assert r['trading_execution_enabled'] is False
