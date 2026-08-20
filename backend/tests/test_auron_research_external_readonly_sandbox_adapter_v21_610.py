import pytest
from app.core.auron_external_provider_contract_registry_v21_609 import ExternalProviderContractRegistry
from app.research.auron_research_external_readonly_sandbox_adapter_v21_610 import ResearchExternalReadonlySandboxAdapter,ResearchExternalReadonlySandboxAdapterError
from app.core.auron_integration_readiness_v21_610 import get_integration_readiness


def build(tmp_path):
    r=ExternalProviderContractRegistry(tmp_path/'contracts.db'); c=r.register(vertical='research',provider_id='research-external-readonly-sandbox',adapter_id='research-external-readonly-sandbox-v1',environment='sandbox',allowed_capabilities=('search-readonly','inspect-source-metadata'),credential_ref='secretref://research/sandbox/read-only'); return ResearchExternalReadonlySandboxAdapter(tmp_path/'adapter.db',r,c.contract_id)

def test_contract_bound_readonly_action_is_persistent_idempotent_and_transport_free(tmp_path):
    a=build(tmp_path); kw=dict(vertical='research',provider_id='research-external-readonly-sandbox',scope='sandbox-search',action_key='search-readonly',payload={'query':'central bank policy'},idempotency_key='k1'); ref=a.execute_canary_action(**kw); assert a.execute_canary_action(**kw)==ref; result=a.read_result(provider_ref=ref); preview=a.preview(ref)
    assert result.state=='completed' and result.external_calls_made==0
    assert preview['state']=='transport-disabled-preview' and preview['credential_resolved'] is False and preview['network_called'] is False and preview['provider_write_performed'] is False

def test_metadata_inspection_is_allowed_without_external_call(tmp_path):
    a=build(tmp_path); ref=a.execute_canary_action(vertical='research',provider_id='research-external-readonly-sandbox',scope='metadata',action_key='inspect-source-metadata',payload={'source_id':'s1'},idempotency_key='k2'); assert a.read_result(provider_ref=ref).external_calls_made==0

def test_write_secret_and_wrong_provider_fail_closed(tmp_path):
    a=build(tmp_path)
    for action,payload in [('publish-result',{'text':'x'}),('search-readonly',{'api_key':'raw'}),('search-readonly',{'delete':True})]:
        with pytest.raises(ResearchExternalReadonlySandboxAdapterError): a.execute_canary_action(vertical='research',provider_id='research-external-readonly-sandbox',scope='x',action_key=action,payload=payload,idempotency_key=str(payload))
    with pytest.raises(ResearchExternalReadonlySandboxAdapterError): a.execute_canary_action(vertical='research',provider_id='other',scope='x',action_key='search-readonly',payload={'query':'x'},idempotency_key='x')

def test_stop_is_persistent(tmp_path):
    a=build(tmp_path); a.stop_canary(activation_id='a1',reason='operator-stop'); assert a.is_stopped('a1') is True

def test_h2_readiness_advances_to_h3_without_transport_or_credential_resolution():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.610' and r['next_item']=='H3-research-external-sandbox-e2e-reconciliation'; assert r['external_provider_network_enabled'] is False and r['external_provider_write_enabled'] is False and r['external_provider_credential_resolution_enabled'] is False and r['live_transports_enabled'] is False
