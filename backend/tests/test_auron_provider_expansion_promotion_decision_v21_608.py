import pytest
from app.core.auron_provider_expansion_promotion_decision_v21_608 import (
    ProviderCanaryEvidence,ProviderExpansionPromotionPolicyV21_608)
from app.core.auron_integration_readiness_v21_608 import get_integration_readiness


def evidence():
    return (
        ProviderCanaryEvidence('research','research-local-readonly',True,True,True,False,False,False,10),
        ProviderCanaryEvidence('instagram-content','instagram-local-draft-preview',True,True,True,False,False,False,20),
        ProviderCanaryEvidence('files-documents','documents-local-readonly',True,True,True,False,False,False,15),
        ProviderCanaryEvidence('communications','communications-local-draft',True,True,True,False,False,False,25),
        ProviderCanaryEvidence('trading','trading-analysis-shadow',True,True,True,False,False,False,55),
    )


def test_complete_safe_evidence_promotes_only_research_readonly_sandbox_design():
    d=ProviderExpansionPromotionPolicyV21_608().evaluate(evidence())
    assert d.outcome=='promote-readonly-sandbox-design'
    assert d.selected_vertical=='research'
    assert d.selected_provider_id=='research-local-readonly'
    assert d.selected_scope=='external-readonly-sandbox-contract-design-only'
    assert d.live_transports_enabled is False
    assert d.trading_live_execution_enabled is False
    assert d.unrestricted_provider_writes_enabled is False


def test_decision_id_is_deterministic_and_input_order_independent():
    p=ProviderExpansionPromotionPolicyV21_608()
    assert p.evaluate(evidence()).decision_id==p.evaluate(tuple(reversed(evidence()))).decision_id


def test_missing_failed_or_duplicate_evidence_holds_fail_closed():
    p=ProviderExpansionPromotionPolicyV21_608()
    missing=p.evaluate(evidence()[:-1])
    assert missing.outcome=='hold' and 'required-canary-evidence-incomplete' in missing.blockers
    bad=list(evidence()); bad[0]=ProviderCanaryEvidence('research','research-local-readonly',True,False,True,False,False,False,10)
    failed=p.evaluate(bad)
    assert failed.outcome=='hold' and 'canary-or-health-certification-incomplete' in failed.blockers
    duplicate=p.evaluate(evidence()+(evidence()[0],))
    assert duplicate.outcome=='hold' and 'duplicate-vertical-evidence' in duplicate.blockers
    with pytest.raises(RuntimeError): p.require_promoted(failed)


def test_any_live_write_or_production_capability_blocks_expansion():
    p=ProviderExpansionPromotionPolicyV21_608(); bad=list(evidence())
    bad[-1]=ProviderCanaryEvidence('trading','trading-analysis-shadow',True,True,False,False,True,False,55)
    d=p.evaluate(bad)
    assert d.outcome=='hold' and 'unsafe-provider-capability-detected' in d.blockers
    assert d.trading_live_execution_enabled is False


def test_invalid_risk_or_missing_provider_identity_blocks_expansion():
    p=ProviderExpansionPromotionPolicyV21_608(); bad=list(evidence())
    bad[0]=ProviderCanaryEvidence('research','',True,True,True,False,False,False,101)
    d=p.evaluate(bad)
    assert d.outcome=='hold'
    assert 'provider-identity-missing' in d.blockers and 'invalid-risk-score' in d.blockers


def test_g21_advances_to_h1_without_enabling_transport():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.608'
    assert r['next_item']=='H1-external-provider-contract-registry-secretless-sandbox-boundary'
    assert r['live_transports_enabled'] is False
    assert r['research_network_transport_enabled'] is False
    assert r['trading_execution_enabled'] is False
    assert r['provider_writes_enabled'] is False
