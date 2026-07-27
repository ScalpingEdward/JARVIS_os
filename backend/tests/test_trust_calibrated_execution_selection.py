import pytest
from app.schemas.trust_calibrated_execution_selection import SelectionCreate
from app.services.trust_calibrated_execution_selection import TrustCalibratedExecutionSelectionService

def payload(**overrides):
    candidate={'adapter_id':'adapter-a','worker_id':'worker-a','capability_match':1.0,'permission_match':1.0,'sandbox_match':1.0,'policy_match':1.0,'trust_score':.95,'reliability':.94,'latency_quality':.90,'freshness':.98,'confidence':.95,'active':True,'risk_brain_blocked':False}
    data={'workspace_id':'ws-a','source_key':'selection-1','requested_by':'operator','operation':'read-status','target':'https://example.test/status','candidates':[candidate]}; data.update(overrides); return SelectionCreate(**data)

def test_status_safety_boundary():
    s=TrustCalibratedExecutionSelectionService().status(); assert s['version']=='21.133'; assert s['external_execution_enabled'] is False; assert s['trading_execution_enabled'] is False

def test_high_trust_candidate_selected_and_can_be_approved():
    s=TrustCalibratedExecutionSelectionService(); r=s.create(payload()); assert r.selected_adapter_id=='adapter-a'; assert not r.risk_flags; r=s.act('ws-a',r.record_id,'approve','owner','op-1'); assert r.approved_by=='owner'

def test_low_trust_candidate_not_eligible():
    s=TrustCalibratedExecutionSelectionService(); p=payload(candidates=[{'adapter_id':'adapter-a','worker_id':'worker-a','capability_match':1.0,'permission_match':1.0,'sandbox_match':1.0,'policy_match':1.0,'trust_score':.3,'reliability':.9,'latency_quality':.9,'freshness':.9,'confidence':.9}]); r=s.create(p); assert 'no-eligible-candidate' in r.risk_flags

def test_permission_mismatch_blocks_candidate():
    s=TrustCalibratedExecutionSelectionService(); p=payload(candidates=[{'adapter_id':'adapter-a','worker_id':'worker-a','capability_match':1.0,'permission_match':.5,'sandbox_match':1.0,'policy_match':1.0,'trust_score':.95,'reliability':.9,'latency_quality':.9,'freshness':.9,'confidence':.9}]); r=s.create(p); assert 'mandatory-control-mismatch' in r.ranked_candidates[0].reasons

def test_protected_operation_hard_blocks():
    s=TrustCalibratedExecutionSelectionService(); r=s.create(payload(operation='trade-execute')); assert 'risk-brain-hard-block' in r.risk_flags; assert r.state.value=='blocked'

def test_replay_isolation_and_duplicate_source():
    s=TrustCalibratedExecutionSelectionService(); r=s.create(payload()); s.act('ws-a',r.record_id,'submit-review','reviewer','same')
    with pytest.raises(ValueError,match='replay'): s.act('ws-a',r.record_id,'approve','owner','same')
    with pytest.raises(KeyError): s.get('ws-b',r.record_id)
    with pytest.raises(ValueError,match='duplicate source_key'): s.create(payload())
