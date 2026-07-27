import pytest
from app.schemas.post_execution_outcome_validation import OutcomeValidationCreate
from app.services.post_execution_outcome_validation import PostExecutionOutcomeValidationService

def payload(**overrides):
    data={
        'workspace_id':'ws-a','source_key':'outcome-1','requested_by':'operator','reconciliation_record_id':'rec-1','reconciliation_digest':'a'*64,'permit_id':'permit-1','authorization_chain_digest':'b'*64,'receipt_digest':'c'*64,'response_digest':'d'*64,'operation':'read-resource','target':'https://example.test/data','method':'GET','receipt_status':'succeeded','postconditions':[{'key':'status','expected':'ready','observed':'ready','passed':True}], 'side_effects':{},'upstream_risk_brain_blocked':False
    }
    data.update(overrides); return OutcomeValidationCreate(**data)

def test_status_keeps_execution_disabled():
    s=PostExecutionOutcomeValidationService().status(); assert s['version']=='21.131'; assert s['external_network_client_enabled'] is False; assert s['write_execution_enabled'] is False; assert s['trading_execution_enabled'] is False

def test_clean_outcome_can_be_attested_after_approval():
    s=PostExecutionOutcomeValidationService(); r=s.create(payload()); assert r.risk_flags==[]; assert r.side_effect_free is True
    r=s.act('ws-a',r.record_id,'approve','owner','op-1'); r=s.act('ws-a',r.record_id,'attest','owner','op-2'); assert r.state.value=='attested'

def test_failed_postcondition_blocks_progression():
    s=PostExecutionOutcomeValidationService(); r=s.create(payload(postconditions=[{'key':'schema','expected':'valid','observed':'invalid','passed':False}])); assert r.state.value=='mismatch'
    with pytest.raises(ValueError,match='findings block progression'): s.act('ws-a',r.record_id,'approve','owner','op-3')

def test_side_effect_detection_blocks_attestation():
    s=PostExecutionOutcomeValidationService(); r=s.create(payload(side_effects={'write_detected':True})); assert 'prohibited-side-effect-detected' in r.risk_flags; assert r.side_effect_free is False

def test_protected_operation_hard_blocks():
    s=PostExecutionOutcomeValidationService(); r=s.create(payload(operation='trade-execute')); assert 'risk-brain-hard-block' in r.risk_flags; assert r.state.value=='blocked'

def test_replay_isolation_and_duplicate_source():
    s=PostExecutionOutcomeValidationService(); r=s.create(payload()); s.act('ws-a',r.record_id,'submit-review','reviewer','same')
    with pytest.raises(ValueError,match='replay'): s.act('ws-a',r.record_id,'approve','owner','same')
    with pytest.raises(KeyError): s.get('ws-b',r.record_id)
    with pytest.raises(ValueError,match='duplicate source_key'): s.create(payload())
