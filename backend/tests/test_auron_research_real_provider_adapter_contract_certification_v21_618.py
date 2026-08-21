from dataclasses import replace

from app.research.auron_research_readonly_network_boundary_e2e_certification_v21_615 import ResearchReadonlyNetworkE2ECertification
from app.research.auron_research_real_provider_activation_readiness_v21_616 import ResearchRealProviderActivationReadinessRequest, ResearchRealProviderActivationReadinessService
from app.research.auron_research_real_provider_adapter_contract_v21_617 import (
    ResearchCredentialResolverContract, ResearchProviderAuditContract,
    ResearchProviderEndpointBinding, ResearchRealProviderAdapterContractRegistry,
)
from app.research.auron_research_real_provider_adapter_contract_certification_v21_618 import (
    ResearchRealProviderAdapterContractCertificationRequest,
    ResearchRealProviderAdapterContractCertificationService,
)
from app.core.auron_integration_readiness_v21_618 import get_integration_readiness


def h7():
    return ResearchReadonlyNetworkE2ECertification('cert-h7','decision-h5','activation-h6','certified',(),2,0,True,True,False,'2026-08-21T13:00:00+00:00')


def h8(tmp_path):
    return ResearchRealProviderActivationReadinessService(tmp_path/'h8.db').evaluate(
        ResearchRealProviderActivationReadinessRequest(h7(),'research-provider-sandbox-v1','sandbox',
            ('https://sandbox.provider.test/search','https://sandbox.provider.test/sources/{source_id}'),
            'secret-manager-reference',True,'operator-1',True,True,True,False))


def contract(tmp_path):
    r=ResearchRealProviderAdapterContractRegistry(tmp_path/'h9.db')
    bindings=(ResearchProviderEndpointBinding('search-readonly','GET','https://sandbox.provider.test/search','research-search-v1'),
              ResearchProviderEndpointBinding('inspect-source-metadata','GET','https://sandbox.provider.test/sources/{source_id}','research-source-metadata-v1'))
    c=r.register(provider_name='research-provider-sandbox-v1',provider_environment='sandbox',adapter_id='research-provider-readonly-v1',
        endpoint_bindings=bindings,credential_resolver=ResearchCredentialResolverContract('secretref://','read-only','bearer-token',False,False),
        audit=ResearchProviderAuditContract(True,True,True,False,False))
    return r,c


def test_clean_h8_and_h9_contract_certify_without_enabling_transport(tmp_path):
    d=h8(tmp_path); r,c=contract(tmp_path); svc=ResearchRealProviderAdapterContractCertificationService(tmp_path/'h10.db',r)
    result=svc.certify(ResearchRealProviderAdapterContractCertificationRequest(d,c.contract_design_id,
        'research-provider-sandbox-v1','sandbox',tuple(b.endpoint_template for b in c.endpoint_bindings)))
    assert result.status=='certified' and result.blockers==()
    assert result.real_network_enabled is False and result.credential_resolution_enabled is False
    assert result.provider_write_enabled is False and result.production_transport_enabled is False
    assert result.requires_separate_adapter_implementation is True


def test_unclean_h8_or_provider_identity_mismatch_fails_closed(tmp_path):
    d=h8(tmp_path); r,c=contract(tmp_path); svc=ResearchRealProviderAdapterContractCertificationService(tmp_path/'h10.db',r)
    bad=replace(d,ready_for_separate_activation_design=False,blockers=('operator-approval-required',))
    a=svc.certify(ResearchRealProviderAdapterContractCertificationRequest(bad,c.contract_design_id,'research-provider-sandbox-v1','sandbox',tuple(b.endpoint_template for b in c.endpoint_bindings)))
    b=svc.certify(ResearchRealProviderAdapterContractCertificationRequest(d,c.contract_design_id,'wrong-provider','sandbox',tuple(x.endpoint_template for x in c.endpoint_bindings)))
    assert 'h8-readiness-not-clean' in a.blockers and 'provider-identity-mismatch' in b.blockers


def test_endpoint_allowlist_mismatch_fails_closed(tmp_path):
    d=h8(tmp_path); r,c=contract(tmp_path); svc=ResearchRealProviderAdapterContractCertificationService(tmp_path/'h10.db',r)
    result=svc.certify(ResearchRealProviderAdapterContractCertificationRequest(d,c.contract_design_id,'research-provider-sandbox-v1','sandbox',('https://sandbox.provider.test/search',)))
    assert result.status=='blocked' and 'endpoint-allowlist-mismatch' in result.blockers


def test_missing_h9_contract_fails_closed(tmp_path):
    d=h8(tmp_path); r,_=contract(tmp_path); svc=ResearchRealProviderAdapterContractCertificationService(tmp_path/'h10.db',r)
    result=svc.certify(ResearchRealProviderAdapterContractCertificationRequest(d,'missing','research-provider-sandbox-v1','sandbox',()))
    assert result.status=='blocked' and 'h9-contract-missing' in result.blockers


def test_h10_readiness_advances_to_h11_without_real_transport():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.618' and r['next_item']=='H11-research-real-provider-adapter-implementation-skeleton'
    assert r['external_provider_network_enabled'] is False and r['external_provider_write_enabled'] is False
    assert r['external_provider_credential_resolution_enabled'] is False and r['real_provider_transport_configured'] is False
    assert r['real_provider_adapter_implemented'] is False
