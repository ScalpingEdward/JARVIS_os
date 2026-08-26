from datetime import datetime,timedelta,timezone
import pytest
from app.research.auron_research_real_provider_activation_boundary_design_v21_621 import ResearchRealProviderActivationBoundaryDesignRegistry,ResearchRealProviderActivationDesignError
from app.core.auron_integration_readiness_v21_621 import get_integration_readiness

def future(): return (datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat()
def valid(r,**kw):
    x=dict(skeleton_certification_id='h12-cert-1',provider_id='research-provider',environment='sandbox',capability='search-readonly',endpoint='https://sandbox.example.test/search',credential_ref='secretref://research/provider/read-only',operator_id='operator-1',max_requests=2,expires_at=future()); x.update(kw); return r.register(**x)

def test_h13_persists_pinned_bounded_design_with_transport_off(tmp_path):
    r=ResearchRealProviderActivationBoundaryDesignRegistry(tmp_path/'d.db'); d=valid(r); assert r.get(d.design_id)==d; assert d.one_shot and d.kill_switch_required and d.rollback_required and d.operator_reapproval_required; assert not d.network_enabled and not d.credential_resolution_enabled and not d.provider_write_enabled and not d.production_transport_enabled

@pytest.mark.parametrize('override',[{'environment':'production'},{'capability':'publish'},{'endpoint':'http://sandbox.example.test/search'},{'credential_ref':'raw-token'},{'max_requests':11},{'kill_switch_required':False},{'rollback_required':False},{'operator_reapproval_required':False}])
def test_h13_rejects_unsafe_designs(tmp_path,override):
    r=ResearchRealProviderActivationBoundaryDesignRegistry(tmp_path/'d.db')
    with pytest.raises(ResearchRealProviderActivationDesignError): valid(r,**override)

def test_h13_readiness_advances_to_h14_without_activation():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.621' and r['next_item']=='H14-research-real-provider-activation-boundary-certification'; assert r['real_provider_activation_enabled'] is False and r['real_provider_transport_configured'] is False and r['external_provider_network_enabled'] is False and r['live_transports_enabled'] is False
