from types import SimpleNamespace
import pytest
from app.research.auron_research_real_provider_adapter_skeleton_e2e_certification_v21_620 import ResearchRealProviderAdapterSkeletonE2ECertifier
from app.research.auron_research_real_provider_adapter_skeleton_v21_619 import ResearchRealProviderAdapterSkeletonError
from app.core.auron_integration_readiness_v21_620 import get_integration_readiness

class NeverResolver:
    def __init__(self): self.calls=0
    def resolve(self,ref): self.calls+=1; raise AssertionError('resolver must not be called')
class NeverTransport:
    def __init__(self): self.calls=[]
    def get(self,**kwargs): self.calls.append(kwargs); raise AssertionError('transport must not be called')
class FakeSkeleton:
    contract_design_id='design-1'
    def __init__(self): self.resolver=NeverResolver(); self.transport=NeverTransport(); self._audit=[]
    def prepare_request_preview(self,*,capability,path_params=None): return SimpleNamespace(method='GET',endpoint='https://sandbox.example.test/search',runtime_transport_enabled=False,credential_reference_required=True,response_schema='research.search.v1')
    def normalize_fixture(self,*,capability,status_code,response_payload):
        import hashlib,json
        normalized={'schema':'research.search.v1','data':response_payload}; h=hashlib.sha256(json.dumps(normalized,sort_keys=True,separators=(',',':')).encode()).hexdigest(); meta={'raw_response_body_persisted':False,'raw_credential_persisted':False,'credential_resolved':False,'network_called':False,'provider_write_performed':False}; self._audit.append({'response_hash':h,'metadata_json':json.dumps(meta)}); return SimpleNamespace(response_schema='research.search.v1',response_hash=h,normalized_payload=normalized)
    def audit_snapshot(self): return tuple(self._audit)
    def execute_live_get(self,*args,**kwargs): raise ResearchRealProviderAdapterSkeletonError('disabled')

def test_h12_certifies_preview_normalization_audit_and_zero_calls(tmp_path):
    s=FakeSkeleton(); c=ResearchRealProviderAdapterSkeletonE2ECertifier(tmp_path/'e2e.db',s).certify(capability='search-readonly',response_payload={'items':[1]}); assert c.status=='certified' and c.blockers==(); assert c.preview_verified and c.normalization_verified and c.audit_integrity_verified and c.execution_fail_closed_verified; assert c.resolver_calls==0 and c.transport_calls==0 and c.real_provider_transport_used is False

def test_h12_blocks_if_live_execution_does_not_fail_closed(tmp_path):
    s=FakeSkeleton(); s.execute_live_get=lambda *a,**k: {'ok':True}; c=ResearchRealProviderAdapterSkeletonE2ECertifier(tmp_path/'e2e.db',s).certify(capability='search-readonly'); assert c.status=='blocked' and 'live-execution-not-fail-closed' in c.blockers

def test_h12_readiness_advances_to_h13_without_activation():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.620' and r['next_item']=='H13-research-real-provider-activation-boundary-design'; assert r['real_provider_activation_enabled'] is False and r['real_provider_transport_configured'] is False and r['external_provider_network_enabled'] is False and r['live_transports_enabled'] is False
