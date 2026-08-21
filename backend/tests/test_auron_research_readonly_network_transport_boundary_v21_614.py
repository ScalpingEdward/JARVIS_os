from datetime import datetime,timezone
import pytest

from app.core.auron_external_provider_contract_registry_v21_609 import ExternalProviderContractRegistry
from app.research.auron_research_external_readonly_sandbox_adapter_v21_610 import ResearchExternalReadonlySandboxAdapter
from app.research.auron_research_external_sandbox_e2e_reconciliation_v21_611 import ResearchExternalSandboxE2EReconciler
from app.research.auron_research_external_sandbox_health_drift_observability_v21_612 import ResearchExternalSandboxHealthDriftObservability
from app.research.auron_research_network_transport_authorization_v21_613 import ResearchNetworkTransportAuthorizationRequest,ResearchNetworkTransportAuthorizationService
from app.research.auron_research_readonly_network_transport_boundary_v21_614 import ResearchReadonlyNetworkTransportBoundary,ResearchReadonlyNetworkBoundaryError
from app.core.auron_integration_readiness_v21_614 import get_integration_readiness


class Resolver:
    def __init__(self): self.calls=0
    def resolve(self, credential_ref): self.calls+=1; assert credential_ref.startswith('secretref://'); return 'resolved-test-token'

class Transport:
    def __init__(self): self.calls=[]
    def get(self,*,endpoint,headers,timeout_seconds):
        self.calls.append((endpoint,headers,timeout_seconds)); return {'status_code':200,'body':{'ok':True}}


def build(tmp_path,with_io=False):
    r=ExternalProviderContractRegistry(tmp_path/'contracts.db'); c=r.register(vertical='research',provider_id='research-external-readonly-sandbox',adapter_id='research-external-readonly-sandbox-v1',environment='sandbox',allowed_capabilities=('search-readonly','inspect-source-metadata'),credential_ref='secretref://research/sandbox/read-only'); a=ResearchExternalReadonlySandboxAdapter(tmp_path/'adapter.db',r,c.contract_id); rec=ResearchExternalSandboxE2EReconciler(tmp_path/'reconcile.db',r,a); ref=a.execute_canary_action(vertical='research',provider_id='research-external-readonly-sandbox',scope='h6',action_key='search-readonly',payload={'query':'x'},idempotency_key='h6'); cert=rec.certify(contract_id=c.contract_id,provider_ref=ref,action_key='search-readonly'); obs=ResearchExternalSandboxHealthDriftObservability(tmp_path/'health.db',r,a,rec,max_age_seconds=300); now=datetime.now(timezone.utc); obs.record(contract_id=c.contract_id,certification_id=cert.certification_id,healthy=True,observed_at=now.isoformat()); auth=ResearchNetworkTransportAuthorizationService(tmp_path/'auth.db',r,a,obs); decision=auth.evaluate(ResearchNetworkTransportAuthorizationRequest(c.contract_id,'operator-1','search-readonly',True,True,True,True),now=now.isoformat()); resolver=Resolver() if with_io else None; transport=Transport() if with_io else None; boundary=ResearchReadonlyNetworkTransportBoundary(tmp_path/'boundary.db',r,a,resolver,transport); return decision,boundary,resolver,transport


def test_positive_h5_decision_can_be_armed_but_io_is_not_injected_by_default(tmp_path):
    decision,boundary,_,_=build(tmp_path); activation=boundary.arm(decision,max_requests=2,timeout_seconds=5); assert activation.active is True and activation.used_requests==0
    with pytest.raises(ResearchReadonlyNetworkBoundaryError): boundary.execute_get(activation_id=activation.activation_id,endpoint='https://sandbox.example.test/read')


def test_explicit_injected_readonly_transport_performs_get_and_counts_budget(tmp_path):
    decision,boundary,resolver,transport=build(tmp_path,with_io=True); activation=boundary.arm(decision,max_requests=2,timeout_seconds=5); result=boundary.execute_get(activation_id=activation.activation_id,endpoint='https://sandbox.example.test/read'); assert result.status_code==200 and result.external_calls_made==1 and result.provider_write_performed is False; assert resolver.calls==1 and len(transport.calls)==1; assert boundary.activation(activation.activation_id).used_requests==1


def test_budget_kill_switch_and_https_fail_closed(tmp_path):
    decision,boundary,_,_=build(tmp_path,with_io=True); activation=boundary.arm(decision,max_requests=1,timeout_seconds=5); boundary.execute_get(activation_id=activation.activation_id,endpoint='https://sandbox.example.test/read')
    with pytest.raises(ResearchReadonlyNetworkBoundaryError): boundary.execute_get(activation_id=activation.activation_id,endpoint='https://sandbox.example.test/read2')
    assert boundary.activation(activation.activation_id).active is False
    decision2,boundary2,_,_=build(tmp_path/'b',with_io=True); a2=boundary2.arm(decision2)
    with pytest.raises(ResearchReadonlyNetworkBoundaryError): boundary2.execute_get(activation_id=a2.activation_id,endpoint='http://unsafe.test/read')
    with pytest.raises(ResearchReadonlyNetworkBoundaryError): boundary2.execute_get(activation_id=a2.activation_id,endpoint='https://sandbox.example.test/read',kill_switch_active=False)
    assert boundary2.activation(a2.activation_id).active is False


def test_negative_h5_decision_cannot_arm(tmp_path):
    decision,boundary,_,_=build(tmp_path); blocked=decision.__class__(decision.decision_id,decision.contract_id,decision.requested_capability,False,('operator-approval-required',),False,False,False,False,True,decision.decided_at)
    with pytest.raises(ResearchReadonlyNetworkBoundaryError): boundary.arm(blocked)


def test_h6_readiness_advances_to_h7_without_enabling_live_transport():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.614' and r['next_item']=='H7-research-readonly-network-boundary-e2e-certification'; assert r['external_provider_network_enabled'] is False and r['external_provider_write_enabled'] is False and r['external_provider_credential_resolution_enabled'] is False and r['live_transports_enabled'] is False
