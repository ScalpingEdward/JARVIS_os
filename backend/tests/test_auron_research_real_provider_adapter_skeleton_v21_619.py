from dataclasses import replace
import pytest

from app.research.auron_research_real_provider_adapter_contract_v21_617 import (
    ResearchCredentialResolverContract, ResearchProviderAuditContract,
    ResearchProviderEndpointBinding, ResearchRealProviderAdapterContractRegistry,
)
from app.research.auron_research_real_provider_adapter_contract_certification_v21_618 import ResearchRealProviderAdapterContractCertification
from app.research.auron_research_real_provider_adapter_skeleton_v21_619 import (
    ResearchRealProviderAdapterSkeleton, ResearchRealProviderAdapterSkeletonError,
)
from app.core.auron_integration_readiness_v21_619 import get_integration_readiness


def build(tmp_path):
    registry=ResearchRealProviderAdapterContractRegistry(tmp_path/'contracts.db')
    contract=registry.register(provider_name='Example Research Sandbox',provider_environment='sandbox',adapter_id='research-example-readonly-v1',
        endpoint_bindings=(
            ResearchProviderEndpointBinding('search-readonly','GET','https://sandbox.provider.test/search','research-search-v1'),
            ResearchProviderEndpointBinding('inspect-source-metadata','GET','https://sandbox.provider.test/sources/{source_id}','research-source-metadata-v1'),),
        credential_resolver=ResearchCredentialResolverContract('secretref://','read-only','bearer-token',False,False),
        audit=ResearchProviderAuditContract(True,True,True,False,False))
    cert=ResearchRealProviderAdapterContractCertification('cert-h10',contract.contract_design_id,'certified',(),False,False,False,False,True,'2026-08-21T14:00:00+00:00')
    return registry,contract,cert


def test_request_preview_is_get_https_and_runtime_disabled(tmp_path):
    r,c,cert=build(tmp_path); a=ResearchRealProviderAdapterSkeleton(tmp_path/'adapter.db',r,c.contract_design_id,cert)
    p=a.prepare_request_preview(capability='search-readonly')
    assert p.method=='GET' and p.endpoint.startswith('https://') and p.runtime_transport_enabled is False
    assert p.credential_reference_required is True


def test_template_params_are_encoded_and_unresolved_params_fail(tmp_path):
    r,c,cert=build(tmp_path); a=ResearchRealProviderAdapterSkeleton(tmp_path/'adapter.db',r,c.contract_design_id,cert)
    p=a.prepare_request_preview(capability='inspect-source-metadata',path_params={'source_id':'abc/123'})
    assert p.endpoint.endswith('/abc%2F123')
    with pytest.raises(ResearchRealProviderAdapterSkeletonError):
        a.prepare_request_preview(capability='inspect-source-metadata')


def test_fixture_normalization_persists_only_audit_safe_evidence(tmp_path):
    r,c,cert=build(tmp_path); a=ResearchRealProviderAdapterSkeleton(tmp_path/'adapter.db',r,c.contract_design_id,cert)
    n=a.normalize_fixture(capability='search-readonly',status_code=200,response_payload={'items':[{'id':'1'}]})
    assert n.response_schema=='research-search-v1' and n.normalized_payload['data']['items'][0]['id']=='1'
    row=a.audit_snapshot()[0]
    assert 'response_hash' in row and 'metadata_json' in row
    assert 'items' not in row['metadata_json'] and 'bearer' not in row['metadata_json'].lower()


def test_live_execution_is_explicitly_disabled_even_with_injected_interfaces(tmp_path):
    class Resolver:
        def resolve(self, credential_ref): raise AssertionError('must not resolve')
    class Transport:
        def get(self, **kwargs): raise AssertionError('must not call network')
    r,c,cert=build(tmp_path); a=ResearchRealProviderAdapterSkeleton(tmp_path/'adapter.db',r,c.contract_design_id,cert,resolver=Resolver(),transport=Transport())
    with pytest.raises(ResearchRealProviderAdapterSkeletonError): a.execute_live_get()


def test_unclean_or_mismatched_h10_certification_fails_closed(tmp_path):
    r,c,cert=build(tmp_path)
    with pytest.raises(ResearchRealProviderAdapterSkeletonError):
        ResearchRealProviderAdapterSkeleton(tmp_path/'a.db',r,c.contract_design_id,replace(cert,status='blocked',blockers=('x',)))
    with pytest.raises(ResearchRealProviderAdapterSkeletonError):
        ResearchRealProviderAdapterSkeleton(tmp_path/'b.db',r,c.contract_design_id,replace(cert,contract_design_id='other'))


def test_h11_readiness_advances_to_h12_without_real_transport():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.619' and r['next_item']=='H12-research-real-provider-adapter-skeleton-certification'
    assert r['real_provider_adapter_runtime_enabled'] is False and r['real_provider_transport_configured'] is False
    assert r['external_provider_network_enabled'] is False and r['external_provider_credential_resolution_enabled'] is False and r['live_transports_enabled'] is False
