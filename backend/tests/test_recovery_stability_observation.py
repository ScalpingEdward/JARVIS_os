from app.services.recovery_stability_observation import RecoveryStabilityObservationService, StabilitySample
import pytest

def good(): return StabilitySample(True,120,.99,True,True,True,1,1)

def test_stable_flow_requires_human_approval():
    s=RecoveryStabilityObservationService(); r=s.create(record_id="r1",workspace_id="ws",source_key="s1",recovery_attestation_id="a1",recovery_attestation_digest="digest123",recovery_attestation_state="attested",operation="read-health",target="primary",samples=[good(),good()])
    assert r.state=="observation-ready"
    s.act("ws","r1","submit-review","u","op1")
    s.act("ws","r1","approve","u","op2")
    assert s.act("ws","r1","close-episode","u","op3").state=="stable"

def test_degraded_confidence_cannot_approve():
    s=RecoveryStabilityObservationService(); bad=StabilitySample(False,4000,.5,False,False,False,.5,.5)
    r=s.create(record_id="r2",workspace_id="ws",source_key="s2",recovery_attestation_id="a2",recovery_attestation_digest="digest123",recovery_attestation_state="attested",operation="read-health",target="primary",samples=[bad])
    assert r.state=="degraded"
    s.act("ws","r2","submit-review","u","op4")
    with pytest.raises(ValueError): s.act("ws","r2","approve","u","op5")

def test_requires_attested_recovery():
    s=RecoveryStabilityObservationService()
    with pytest.raises(ValueError): s.create(record_id="r3",workspace_id="ws",source_key="s3",recovery_attestation_id="a3",recovery_attestation_digest="digest123",recovery_attestation_state="review-required",operation="read-health",target="primary",samples=[good()])

def test_risk_brain_hard_block():
    s=RecoveryStabilityObservationService(); r=s.create(record_id="r4",workspace_id="ws",source_key="s4",recovery_attestation_id="a4",recovery_attestation_digest="digest123",recovery_attestation_state="attested",operation="trade-execute",target="primary",samples=[good()])
    assert r.state=="blocked"
    with pytest.raises(ValueError): s.act("ws","r4","submit-review","u","op6")

def test_replay_and_workspace_isolation():
    s=RecoveryStabilityObservationService(); s.create(record_id="r5",workspace_id="ws1",source_key="same",recovery_attestation_id="a5",recovery_attestation_digest="digest123",recovery_attestation_state="attested",operation="read-health",target="primary",samples=[good()])
    with pytest.raises(ValueError): s.create(record_id="r6",workspace_id="ws1",source_key="same",recovery_attestation_id="a6",recovery_attestation_digest="digest123",recovery_attestation_state="attested",operation="read-health",target="primary",samples=[good()])
    r=s.create(record_id="r7",workspace_id="ws2",source_key="same",recovery_attestation_id="a7",recovery_attestation_digest="digest123",recovery_attestation_state="attested",operation="read-health",target="primary",samples=[good()]); assert r.workspace_id=="ws2"
