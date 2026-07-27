import pytest
from app.schemas.trust_calibrated_dispatch_planning_failover import DispatchPlanCreate
from app.services.trust_calibrated_dispatch_planning_failover import TrustCalibratedDispatchPlanningFailoverService

def payload(operation="read-status", candidates=None):
    if candidates is None:
        candidates=[
            {"adapter_id":"adapter-a","worker_id":"worker-a","selection_record_id":"sel-a","selection_digest":"dig-a","trust_score":.96,"reliability":.95,"latency_quality":.90,"confidence":.95,"freshness":.95},
            {"adapter_id":"adapter-b","worker_id":"worker-b","selection_record_id":"sel-b","selection_digest":"dig-b","trust_score":.90,"reliability":.92,"latency_quality":.95,"confidence":.90,"freshness":.90},
        ]
    return DispatchPlanCreate(workspace_id="ws-a",source_key="dispatch-plan",requested_by="operator",operation=operation,target="https://example.com/status",authorization_chain_id="chain-1",authorization_chain_digest="chain-digest",candidates=candidates)

def test_status_disables_dispatch_and_autofailover():
    s=TrustCalibratedDispatchPlanningFailoverService().status(); assert s["version"]=="21.134"; assert s["dispatch_execution_enabled"] is False; assert s["autonomous_failover_enabled"] is False

def test_primary_and_standby_ranked():
    s=TrustCalibratedDispatchPlanningFailoverService(); r=s.create(payload()); assert r.primary is not None and r.standby is not None; assert r.primary.score>=r.standby.score; assert r.state.value=="review-required"

def test_human_approval_required_before_ready():
    s=TrustCalibratedDispatchPlanningFailoverService(); r=s.create(payload())
    with pytest.raises(ValueError,match="human approval"): s.act("ws-a",r.record_id,"mark-ready","owner","op-1")
    r=s.act("ws-a",r.record_id,"approve","owner","op-2"); r=s.act("ws-a",r.record_id,"mark-ready","owner","op-3"); assert r.state.value=="ready"

def test_mandatory_control_mismatch_excluded():
    c=payload().candidates; c[0].permission_match=False
    s=TrustCalibratedDispatchPlanningFailoverService(); r=s.create(payload(candidates=[x.model_dump() for x in c])); bad=[x for x in r.ranked_candidates if x.adapter_id=="adapter-a"][0]; assert bad.eligible is False; assert "permission-mismatch" in bad.reasons

def test_protected_operation_hard_blocks():
    s=TrustCalibratedDispatchPlanningFailoverService(); r=s.create(payload(operation="trade-execute")); assert r.state.value=="blocked"; assert any(x.startswith("risk-brain-hard-block") for x in r.risk_flags)

def test_failover_requires_standby():
    c=payload().candidates; c[1].active=False
    s=TrustCalibratedDispatchPlanningFailoverService(); r=s.create(payload(candidates=[x.model_dump() for x in c])); assert "insufficient-failover-coverage" in r.risk_flags
    with pytest.raises(ValueError,match="standby failover unavailable"): s.act("ws-a",r.record_id,"require-failover","owner","op-f")

def test_replay_isolation_duplicate_source():
    s=TrustCalibratedDispatchPlanningFailoverService(); r=s.create(payload()); s.act("ws-a",r.record_id,"mark-degraded","reviewer","same")
    with pytest.raises(ValueError,match="replay"): s.act("ws-a",r.record_id,"suspend","reviewer","same")
    with pytest.raises(KeyError): s.get("ws-b",r.record_id)
    with pytest.raises(ValueError,match="duplicate source_key"): s.create(payload())
