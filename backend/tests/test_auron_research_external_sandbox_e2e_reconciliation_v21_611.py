from app.core.auron_external_provider_contract_registry_v21_609 import ExternalProviderContractRegistry
from app.research.auron_research_external_readonly_sandbox_adapter_v21_610 import ResearchExternalReadonlySandboxAdapter
from app.research.auron_research_external_sandbox_e2e_reconciliation_v21_611 import ResearchExternalSandboxE2EReconciler
from app.core.auron_integration_readiness_v21_611 import get_integration_readiness

def build(tmp_path):
    r=ExternalProviderContractRegistry(tmp_path/'contracts.db'); c=r.register(vertical='research',provider_id='research-external-readonly-sandbox',adapter_id='research-external-readonly-sandbox-v1',environment='sandbox',allowed_capabilities=('search-readonly','inspect-source-metadata'),credential_ref='secretref://research/sandbox/read-only'); a=ResearchExternalReadonlySandboxAdapter(tmp_path/'adapter.db',r,c.contract_id); x=ResearchExternalSandboxE2EReconciler(tmp_path/'reconcile.db',r,a); return r,c,a,x

def test_h1_h2_e2e_path_certifies_with_zero_external_calls(tmp_path):
    r,c,a,x=build(tmp_path); ref=a.execute_canary_action(vertical='research',provider_id='research-external-readonly-sandbox',scope='cert',action_key='search-readonly',payload={'query':'rates'},idempotency_key='e2e-1'); cert=x.certify(contract_id=c.contract_id,provider_ref=ref,action_key='search-readonly'); assert cert.status=='certified' and cert.blockers==() and cert.external_calls_made==0; assert x.get(cert.certification_id).status=='certified'

def test_missing_evidence_fails_closed(tmp_path):
    r,c,a,x=build(tmp_path); cert=x.certify(contract_id=c.contract_id,provider_ref='missing',action_key='search-readonly'); assert cert.status=='blocked' and 'provider-evidence-missing' in cert.blockers

def test_wrong_contract_and_unbound_capability_fail_closed(tmp_path):
    r,c,a,x=build(tmp_path); other=r.register(vertical='research',provider_id='other',adapter_id='other-adapter',environment='sandbox',allowed_capabilities=('search-readonly',)); ref=a.execute_canary_action(vertical='research',provider_id='research-external-readonly-sandbox',scope='cert',action_key='search-readonly',payload={'query':'x'},idempotency_key='e2e-2'); cert=x.certify(contract_id=other.contract_id,provider_ref=ref,action_key='publish-result'); assert cert.status=='blocked'; assert 'adapter-contract-mismatch' in cert.blockers and 'contract-identity-mismatch' in cert.blockers and 'capability-not-bound' in cert.blockers

def test_h3_readiness_advances_to_h4_without_transport():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.611' and r['next_item']=='H4-research-external-sandbox-health-drift-observability'; assert r['external_provider_network_enabled'] is False and r['external_provider_write_enabled'] is False and r['external_provider_credential_resolution_enabled'] is False and r['live_transports_enabled'] is False
