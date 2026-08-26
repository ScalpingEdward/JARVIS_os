from dataclasses import replace
from datetime import datetime,timedelta,timezone
import pytest
from app.research.auron_research_real_provider_activation_boundary_design_v21_621 import ResearchRealProviderActivationBoundaryDesignRegistry
from app.research.auron_research_real_provider_activation_boundary_certification_v21_622 import ResearchRealProviderActivationBoundaryCertification
from app.research.auron_research_real_provider_one_shot_canary_activation_gate_v21_623 import ResearchRealProviderOneShotCanaryActivationGate,ResearchRealProviderCanaryActivationGateError
from app.core.auron_integration_readiness_v21_623 import get_integration_readiness

def design(tmp_path):
    r=ResearchRealProviderActivationBoundaryDesignRegistry(tmp_path/'d.db'); return r.register(skeleton_certification_id='h12-cert',provider_id='research-provider',environment='sandbox',capability='search-readonly',endpoint='https://sandbox.example.test/search',credential_ref='secretref://research/provider/read-only',operator_id='operator-1',max_requests=2,expires_at=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat())
def cert(d): return ResearchRealProviderActivationBoundaryCertification('h14-cert',d.design_id,'certified',(),True,True,True,True,datetime.now(timezone.utc).isoformat())

def test_h15_issues_short_lived_non_executable_one_shot_token(tmp_path):
    d=design(tmp_path); g=ResearchRealProviderOneShotCanaryActivationGate(tmp_path/'g.db'); t=g.issue(cert(d),d,operator_id='operator-1',operator_reapproved=True,kill_switch_ready=True,rollback_ready=True,ttl_seconds=120); assert t.state=='armed-not-executable'; assert t.request_budget==2; assert not t.network_execution_enabled and not t.credential_resolution_enabled and not t.provider_write_enabled and not t.production_transport_enabled; assert g.issue(cert(d),d,operator_id='operator-1',operator_reapproved=True,kill_switch_ready=True,rollback_ready=True).token_id==t.token_id

def test_h15_requires_clean_h14_and_operator_reapproval(tmp_path):
    d=design(tmp_path); g=ResearchRealProviderOneShotCanaryActivationGate(tmp_path/'g.db')
    with pytest.raises(ResearchRealProviderCanaryActivationGateError): g.issue(replace(cert(d),status='blocked',blockers=('x',)),d,operator_id='operator-1',operator_reapproved=True,kill_switch_ready=True,rollback_ready=True)
    with pytest.raises(ResearchRealProviderCanaryActivationGateError): g.issue(cert(d),d,operator_id='operator-1',operator_reapproved=False,kill_switch_ready=True,rollback_ready=True)

def test_h15_revoke_is_operator_bound(tmp_path):
    d=design(tmp_path); g=ResearchRealProviderOneShotCanaryActivationGate(tmp_path/'g.db'); t=g.issue(cert(d),d,operator_id='operator-1',operator_reapproved=True,kill_switch_ready=True,rollback_ready=True)
    with pytest.raises(ResearchRealProviderCanaryActivationGateError): g.revoke(t.token_id,operator_id='other')
    assert g.revoke(t.token_id,operator_id='operator-1').state=='revoked'

def test_h15_readiness_advances_to_h16_without_execution():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.623' and r['next_item']=='H16-research-real-provider-canary-execution-boundary-design'; assert r['real_provider_canary_token_enabled'] is True and r['real_provider_canary_execution_enabled'] is False and r['external_provider_network_enabled'] is False and r['live_transports_enabled'] is False
