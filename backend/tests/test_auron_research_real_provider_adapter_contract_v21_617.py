import pytest

from app.research.auron_research_real_provider_adapter_contract_v21_617 import (
    ResearchCredentialResolverContract, ResearchProviderAuditContract,
    ResearchProviderEndpointBinding, ResearchRealProviderAdapterContractError,
    ResearchRealProviderAdapterContractRegistry,
)
from app.core.auron_integration_readiness_v21_617 import get_integration_readiness


def resolver():
    return ResearchCredentialResolverContract('secretref://','read-only','bearer-token',False,False)


def audit():
    return ResearchProviderAuditContract(True,True,True,False,False)


def test_readonly_provider_contract_is_persistent_and_design_only(tmp_path):
    r=ResearchRealProviderAdapterContractRegistry(tmp_path/'contracts.db')
    bindings=(ResearchProviderEndpointBinding('search-readonly','GET','https://sandbox.provider.test/search','research-search-v1'),
              ResearchProviderEndpointBinding('inspect-source-metadata','GET','https://sandbox.provider.test/sources/{source_id}','research-source-metadata-v1'))
    c=r.register(provider_name='Example Research Sandbox',provider_environment='sandbox',adapter_id='research-example-readonly-v1',endpoint_bindings=bindings,credential_resolver=resolver(),audit=audit())
    loaded=r.get(c.contract_design_id)
    assert loaded==c
    assert c.network_implementation_included is False and c.provider_client_included is False
    assert c.write_methods_allowed is False and c.production_transport_allowed is False


def test_non_get_non_https_and_unapproved_capability_fail_closed(tmp_path):
    r=ResearchRealProviderAdapterContractRegistry(tmp_path/'contracts.db')
    bad=(ResearchProviderEndpointBinding('search-readonly','POST','https://sandbox.provider.test/search','v1'),)
    with pytest.raises(ResearchRealProviderAdapterContractError): r.register(provider_name='x',provider_environment='sandbox',adapter_id='a',endpoint_bindings=bad,credential_resolver=resolver(),audit=audit())
    bad=(ResearchProviderEndpointBinding('search-readonly','GET','http://sandbox.provider.test/search','v1'),)
    with pytest.raises(ResearchRealProviderAdapterContractError): r.register(provider_name='x',provider_environment='sandbox',adapter_id='a',endpoint_bindings=bad,credential_resolver=resolver(),audit=audit())
    bad=(ResearchProviderEndpointBinding('publish-result','GET','https://sandbox.provider.test/x','v1'),)
    with pytest.raises(ResearchRealProviderAdapterContractError): r.register(provider_name='x',provider_environment='sandbox',adapter_id='a',endpoint_bindings=bad,credential_resolver=resolver(),audit=audit())


def test_production_raw_secrets_and_raw_response_audit_are_forbidden(tmp_path):
    r=ResearchRealProviderAdapterContractRegistry(tmp_path/'contracts.db'); bindings=(ResearchProviderEndpointBinding('search-readonly','GET','https://sandbox.provider.test/search','v1'),)
    with pytest.raises(ResearchRealProviderAdapterContractError): r.register(provider_name='x',provider_environment='production',adapter_id='a',endpoint_bindings=bindings,credential_resolver=resolver(),audit=audit())
    unsafe_resolver=ResearchCredentialResolverContract('secretref://','read-only','bearer-token',True,False)
    with pytest.raises(ResearchRealProviderAdapterContractError): r.register(provider_name='x',provider_environment='sandbox',adapter_id='a',endpoint_bindings=bindings,credential_resolver=unsafe_resolver,audit=audit())
    unsafe_audit=ResearchProviderAuditContract(True,True,True,False,True)
    with pytest.raises(ResearchRealProviderAdapterContractError): r.register(provider_name='x',provider_environment='sandbox',adapter_id='a',endpoint_bindings=bindings,credential_resolver=resolver(),audit=unsafe_audit)


def test_h9_readiness_advances_to_h10_without_real_provider_transport():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.617' and r['next_item']=='H10-research-real-provider-adapter-contract-certification'
    assert r['real_provider_transport_configured'] is False and r['real_provider_adapter_implemented'] is False
    assert r['external_provider_network_enabled'] is False and r['live_transports_enabled'] is False
