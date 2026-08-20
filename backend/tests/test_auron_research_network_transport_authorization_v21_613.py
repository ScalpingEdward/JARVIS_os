from datetime import datetime,timezone
from app.core.auron_external_provider_contract_registry_v21_609 import ExternalProviderContractRegistry
from app.research.auron_research_external_readonly_sandbox_adapter_v21_610 import ResearchExternalReadonlySandboxAdapter
from app.research.auron_research_external_sandbox_e2e_reconciliation_v21_611 import ResearchExternalSandboxE2EReconciler
from app.research.auron_research_external_sandbox_health_drift_observability_v21_612 import ResearchExternalSandboxHealthDriftObservability
from app.research.auron_research_network_transport_authorization_v21_613 import ResearchNetworkTransportAuthorizationRequest,ResearchNetworkTransportAuthorizationService
from app.core.auron_integration_readiness_v21_613 import get_integration_readiness


def build(tmp_path):
    r=ExternalProviderContractRegistry(tmp_path/'contracts.db'); c=r.register(vertical='research',provider_id='research-external-readonly-sandbox',adapter_id='research-external-readonly-sandbox-v1',environment='sandbox',allowed_capabilities=('search-readonly','inspect-source-metadata'),credential_ref='secretref://research/sandbox/read-only'); a=ResearchExternalReadonlySandboxAdapter(tmp_path/'adapter.db',r,c.contract_id); rec=ResearchExternalSandboxE2EReconciler(tmp_path/'reconcile.db',r,a); ref=a.execute_canary_action(vertical='research',provider_id='research-external-readonly-sandbox',scope='h5',action_key='search-readonly',payload={'query':'x'},idempotency_key='h5'); cert=rec.certify(contract_id=c.contract_id,provider_ref=ref,action_key='search-readonly'); obs=ResearchExternalSandboxHealthDriftObservability(tmp_path/'health.db',r,a,rec,max_age_seconds=300); now=datetime.now(timezone.utc); obs.record(contract_id=c.contract_id,certification_id=cert.certification_id,healthy=True,observed_at=now.isoformat()); svc=ResearchNetworkTransportAuthorizationService(tmp_path/'auth.db',r,a,obs); return c,svc,now


def request(c,**overrides):
    values=dict(contract_id=c.contract_id,operator_id='operator-1',requested_capability='search-readonly',operator_approved=True,rollback_control_ready=True,stop_control_ready=True,credential_reference_present=True); values.update(overrides); return ResearchNetworkTransportAuthorizationRequest(**values)


def test_valid_h1_h4_evidence_authorizes_decision_but_does_not_enable_transport(tmp_path):
    c,svc,now=build(tmp_path); d=svc.evaluate(request(c),now=now.isoformat()); assert d.authorized is True and d.blockers==(); assert d.network_transport_enabled is False and d.credential_resolution_enabled is False and d.provider_write_enabled is False and d.production_transport_enabled is False and d.requires_separate_activation is True


def test_missing_operator_approval_or_stop_control_fails_closed(tmp_path):
    c,svc,now=build(tmp_path); a=svc.evaluate(request(c,operator_approved=False),now=now.isoformat()); b=svc.evaluate(request(c,stop_control_ready=False),now=now.isoformat()); assert a.authorized is False and 'operator-approval-required' in a.blockers; assert b.authorized is False and 'stop-control-not-ready' in b.blockers


def test_unbound_capability_or_credential_state_mismatch_fails_closed(tmp_path):
    c,svc,now=build(tmp_path); a=svc.evaluate(request(c,requested_capability='publish-result'),now=now.isoformat()); b=svc.evaluate(request(c,credential_reference_present=False),now=now.isoformat()); assert a.authorized is False and 'capability-not-in-contract' in a.blockers; assert b.authorized is False and 'credential-reference-state-mismatch' in b.blockers


def test_h5_readiness_advances_to_h6_without_enabling_network():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.613' and r['next_item']=='H6-research-readonly-network-transport-boundary'; assert r['external_provider_network_enabled'] is False and r['external_provider_write_enabled'] is False and r['external_provider_credential_resolution_enabled'] is False and r['live_transports_enabled'] is False
