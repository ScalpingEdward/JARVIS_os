from dataclasses import replace

from app.research.auron_research_readonly_network_boundary_e2e_certification_v21_615 import ResearchReadonlyNetworkE2ECertification
from app.research.auron_research_real_provider_activation_readiness_v21_616 import ResearchRealProviderActivationReadinessRequest, ResearchRealProviderActivationReadinessService
from app.core.auron_integration_readiness_v21_616 import get_integration_readiness


def h7():
    return ResearchReadonlyNetworkE2ECertification('cert-h7','decision-h5','activation-h6','certified',(),2,0,True,True,False,'2026-08-21T13:00:00+00:00')


def request(**overrides):
    values=dict(h7_certification=h7(),provider_id='research-provider-sandbox-v1',provider_environment='sandbox',
        endpoint_allowlist=('https://sandbox.example.test/search',),credential_provenance='secret-manager-reference',
        credential_scope_read_only=True,operator_id='operator-1',operator_approved=True,
        rollback_control_ready=True,stop_control_ready=True,production_transport_requested=False)
    values.update(overrides); return ResearchRealProviderActivationReadinessRequest(**values)


def test_clean_h7_and_safe_provider_evidence_yields_decision_only_readiness(tmp_path):
    d=ResearchRealProviderActivationReadinessService(tmp_path/'h8.db').evaluate(request())
    assert d.ready_for_separate_activation_design is True and d.blockers==()
    assert d.real_network_enabled is False and d.credential_resolution_enabled is False
    assert d.provider_write_enabled is False and d.production_transport_enabled is False
    assert d.requires_separate_provider_adapter is True and d.requires_separate_activation is True


def test_unclean_h7_or_production_environment_fails_closed(tmp_path):
    svc=ResearchRealProviderActivationReadinessService(tmp_path/'h8.db')
    bad_h7=replace(h7(),status='blocked',blockers=('budget-stop-not-enforced',))
    a=svc.evaluate(request(h7_certification=bad_h7)); b=svc.evaluate(request(provider_environment='production'))
    assert a.ready_for_separate_activation_design is False and 'h7-certification-not-clean' in a.blockers
    assert b.ready_for_separate_activation_design is False and 'provider-environment-must-be-nonproduction' in b.blockers


def test_bad_allowlist_or_credential_provenance_fails_closed(tmp_path):
    svc=ResearchRealProviderActivationReadinessService(tmp_path/'h8.db')
    a=svc.evaluate(request(endpoint_allowlist=('http://unsafe.example.test/search',)))
    b=svc.evaluate(request(credential_provenance='raw-secret'))
    c=svc.evaluate(request(credential_scope_read_only=False))
    assert 'endpoint-allowlist-invalid' in a.blockers
    assert 'credential-provenance-unsafe' in b.blockers
    assert 'credential-scope-not-readonly' in c.blockers


def test_missing_operator_or_controls_and_production_request_fail_closed(tmp_path):
    svc=ResearchRealProviderActivationReadinessService(tmp_path/'h8.db')
    a=svc.evaluate(request(operator_approved=False)); b=svc.evaluate(request(stop_control_ready=False)); c=svc.evaluate(request(production_transport_requested=True))
    assert 'operator-approval-required' in a.blockers and 'stop-control-not-ready' in b.blockers
    assert 'production-transport-out-of-scope' in c.blockers


def test_h8_readiness_advances_to_h9_without_real_network():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.616' and r['next_item']=='H9-research-real-provider-adapter-contract-design'
    assert r['external_provider_network_enabled'] is False and r['external_provider_write_enabled'] is False
    assert r['external_provider_credential_resolution_enabled'] is False and r['real_provider_transport_configured'] is False
