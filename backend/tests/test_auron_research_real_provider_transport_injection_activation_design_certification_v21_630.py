from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.core.auron_integration_readiness_v21_630 import get_integration_readiness
from app.research.auron_research_real_provider_one_shot_canary_execution_gate_v21_626 import ResearchRealProviderCanaryExecutionSession
from app.research.auron_research_real_provider_transport_injection_contract_v21_627 import ResearchRealProviderTransportInjectionContract
from app.research.auron_research_real_provider_transport_injection_contract_certification_v21_628 import ResearchRealProviderTransportInjectionContractCertification
from app.research.auron_research_real_provider_transport_injection_activation_design_v21_629 import ResearchRealProviderTransportInjectionActivationDesign
from app.research.auron_research_real_provider_transport_injection_activation_design_certification_v21_630 import ResearchRealProviderTransportInjectionActivationDesignCertifier


def session():
    now = datetime.now(timezone.utc)
    return ResearchRealProviderCanaryExecutionSession('session-1','h17-cert','boundary-1','token-1','operator-1','research-provider','search-readonly','https://sandbox.example.test/search',2,0,'token-consumed-session-open-transport-disabled',now.isoformat(),(now+timedelta(minutes=5)).isoformat(),False,False,False,False,False)


def contract(s):
    return ResearchRealProviderTransportInjectionContract('contract-1',s.session_id,s.provider_id,s.capability,s.endpoint,'GET',s.request_budget,10,1048576,'defined-not-injected',True,True,True,True,False,False,False,False,False)


def h20(c,s):
    return ResearchRealProviderTransportInjectionContractCertification('h20-cert',c.contract_id,s.session_id,'certified',(),True,True,True,True,True,True,datetime.now(timezone.utc).isoformat())


def design(c,s):
    return ResearchRealProviderTransportInjectionActivationDesign('design-1','h20-cert',c.contract_id,s.session_id,'operator-1',c.provider_id,c.capability,c.endpoint,'GET',c.request_budget,c.timeout_seconds,c.max_response_bytes,'transportref://research/future-readonly','designed-not-authorized-not-injected',True,True,True,True,True,True,True,False,False,False,False,False,False,datetime.now(timezone.utc).isoformat())


def test_h22_certifies_exact_binding_controls_and_zero_transport(tmp_path):
    s=session(); c=contract(s); cert=h20(c,s); d=design(c,s)
    result=ResearchRealProviderTransportInjectionActivationDesignCertifier(tmp_path/'h22.db').certify(d,cert,c,s)
    assert result.status=='certified' and result.blockers==()
    assert result.exact_binding_verified and result.opaque_reference_verified
    assert result.safety_controls_verified and result.zero_authorization_transport_verified


def test_h22_blocks_binding_drift(tmp_path):
    s=session(); c=contract(s); cert=h20(c,s); d=replace(design(c,s),provider_id='wrong-provider')
    result=ResearchRealProviderTransportInjectionActivationDesignCertifier(tmp_path/'h22.db').certify(d,cert,c,s)
    assert result.status=='blocked' and 'h21-h20-h19-h18-binding-mismatch' in result.blockers


def test_h22_blocks_transport_or_authorization_enablement(tmp_path):
    s=session(); c=contract(s); cert=h20(c,s); d=replace(design(c,s),injection_authorized=True)
    result=ResearchRealProviderTransportInjectionActivationDesignCertifier(tmp_path/'h22.db').certify(d,cert,c,s)
    assert result.status=='blocked' and 'authorization-transport-or-write-already-enabled' in result.blockers


def test_h22_readiness_advances_to_h23_without_transport_authorization():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.630'
    assert r['next_item']=='H23-research-real-provider-transport-injection-authorization-gate'
    assert r['real_provider_transport_injection_activation_certified'] is True
    assert r['real_provider_transport_injection_authorized'] is False
    assert r['real_provider_canary_transport_enabled'] is False
    assert r['live_transports_enabled'] is False
