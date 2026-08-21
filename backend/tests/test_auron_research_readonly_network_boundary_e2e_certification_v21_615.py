from dataclasses import replace
from datetime import datetime, timezone
import pytest

from app.core.auron_external_provider_contract_registry_v21_609 import ExternalProviderContractRegistry
from app.research.auron_research_external_readonly_sandbox_adapter_v21_610 import ResearchExternalReadonlySandboxAdapter
from app.research.auron_research_external_sandbox_e2e_reconciliation_v21_611 import ResearchExternalSandboxE2EReconciler
from app.research.auron_research_external_sandbox_health_drift_observability_v21_612 import ResearchExternalSandboxHealthDriftObservability
from app.research.auron_research_network_transport_authorization_v21_613 import ResearchNetworkTransportAuthorizationRequest, ResearchNetworkTransportAuthorizationService
from app.research.auron_research_readonly_network_transport_boundary_v21_614 import ResearchReadonlyNetworkTransportBoundary
from app.research.auron_research_readonly_network_boundary_e2e_certification_v21_615 import ResearchReadonlyNetworkBoundaryE2ECertifier, ResearchReadonlyNetworkE2ECertificationError
from app.core.auron_integration_readiness_v21_615 import get_integration_readiness


class FakeResolver:
    def __init__(self): self.calls=0
    def resolve(self, credential_ref): self.calls+=1; assert credential_ref.startswith('secretref://'); return 'fake-test-token'


class FakeTransport:
    def __init__(self): self.calls=[]
    def get(self, *, endpoint, headers, timeout_seconds):
        self.calls.append((endpoint,headers,timeout_seconds)); return {'status_code':200,'json':{'ok':True}}


def build(tmp_path):
    r=ExternalProviderContractRegistry(tmp_path/'contracts.db'); c=r.register(vertical='research',provider_id='research-external-readonly-sandbox',adapter_id='research-external-readonly-sandbox-v1',environment='sandbox',allowed_capabilities=('search-readonly','inspect-source-metadata'),credential_ref='secretref://research/sandbox/read-only')
    a=ResearchExternalReadonlySandboxAdapter(tmp_path/'adapter.db',r,c.contract_id); rec=ResearchExternalSandboxE2EReconciler(tmp_path/'reconcile.db',r,a)
    ref=a.execute_canary_action(vertical='research',provider_id='research-external-readonly-sandbox',scope='h7',action_key='search-readonly',payload={'query':'x'},idempotency_key='h7'); cert=rec.certify(contract_id=c.contract_id,provider_ref=ref,action_key='search-readonly')
    obs=ResearchExternalSandboxHealthDriftObservability(tmp_path/'health.db',r,a,rec,max_age_seconds=300); now=datetime.now(timezone.utc); obs.record(contract_id=c.contract_id,certification_id=cert.certification_id,healthy=True,observed_at=now.isoformat())
    auth=ResearchNetworkTransportAuthorizationService(tmp_path/'auth.db',r,a,obs); d=auth.evaluate(ResearchNetworkTransportAuthorizationRequest(c.contract_id,'operator-1','search-readonly',True,True,True,True),now=now.isoformat())
    resolver=FakeResolver(); transport=FakeTransport(); boundary=ResearchReadonlyNetworkTransportBoundary(tmp_path/'boundary.db',r,a,resolver=resolver,transport=transport)
    return d,resolver,transport,boundary


def test_h5_h6_e2e_certifies_fake_readonly_transport_budget_and_stop(tmp_path):
    d,resolver,transport,b=build(tmp_path); result=ResearchReadonlyNetworkBoundaryE2ECertifier(tmp_path/'e2e.db',b).certify(d,endpoint='https://sandbox.example.test/search',max_requests=2,timeout_seconds=5)
    assert result.status=='certified' and result.blockers==() and result.calls_observed==2
    assert result.provider_writes_observed==0 and result.budget_enforced is True and result.stop_enforced is True
    assert result.real_provider_transport_used is False and resolver.calls==2 and len(transport.calls)==2


def test_unauthorized_h5_decision_is_rejected_before_activation(tmp_path):
    d,_,_,b=build(tmp_path); bad=replace(d,authorized=False,blockers=('operator-approval-required',))
    with pytest.raises(ResearchReadonlyNetworkE2ECertificationError): ResearchReadonlyNetworkBoundaryE2ECertifier(tmp_path/'e2e.db',b).certify(bad,endpoint='https://sandbox.example.test/search')


def test_h7_readiness_advances_to_h8_without_real_provider_transport():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.615' and r['next_item']=='H8-research-network-provider-activation-readiness-decision'
    assert r['real_provider_transport_configured'] is False and r['external_provider_network_enabled'] is False and r['external_provider_write_enabled'] is False and r['live_transports_enabled'] is False
