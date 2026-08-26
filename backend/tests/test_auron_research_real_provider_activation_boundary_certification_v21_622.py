from dataclasses import replace
from datetime import datetime,timedelta,timezone
from app.research.auron_research_real_provider_activation_boundary_design_v21_621 import ResearchRealProviderActivationBoundaryDesignRegistry
from app.research.auron_research_real_provider_activation_boundary_certification_v21_622 import ResearchRealProviderActivationBoundaryCertifier
from app.core.auron_integration_readiness_v21_622 import get_integration_readiness

def design(tmp_path):
    r=ResearchRealProviderActivationBoundaryDesignRegistry(tmp_path/'d.db'); expiry=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat(); return r.register(skeleton_certification_id='h12-cert',provider_id='research-provider',environment='sandbox',capability='search-readonly',endpoint='https://sandbox.example.test/search',credential_ref='secretref://research/provider/read-only',operator_id='operator-1',max_requests=2,expires_at=expiry)
def certify(tmp_path,d): return ResearchRealProviderActivationBoundaryCertifier(tmp_path/'c.db').certify(d,expected_skeleton_certification_id='h12-cert',expected_provider_id='research-provider',expected_environment='sandbox',expected_capability='search-readonly',allowed_endpoints=('https://sandbox.example.test/search',),expected_credential_ref='secretref://research/provider/read-only')

def test_h14_certifies_exact_pinning_budget_controls_and_zero_transport(tmp_path):
    c=certify(tmp_path,design(tmp_path)); assert c.status=='certified' and c.blockers==(); assert c.identity_pinning_verified and c.expiry_budget_verified and c.safety_controls_verified and c.zero_transport_verified

def test_h14_blocks_identity_drift(tmp_path):
    d=replace(design(tmp_path),provider_id='wrong-provider'); c=certify(tmp_path,d); assert c.status=='blocked' and 'identity-or-pinning-mismatch' in c.blockers

def test_h14_blocks_transport_enablement(tmp_path):
    d=replace(design(tmp_path),network_enabled=True); c=certify(tmp_path,d); assert c.status=='blocked' and 'transport-or-write-enabled' in c.blockers

def test_h14_readiness_advances_to_h15_without_activation():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.622' and r['next_item']=='H15-research-real-provider-one-shot-canary-activation-gate'; assert r['real_provider_activation_enabled'] is False and r['real_provider_transport_configured'] is False and r['live_transports_enabled'] is False
