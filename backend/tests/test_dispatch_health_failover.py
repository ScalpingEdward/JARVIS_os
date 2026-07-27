import pytest
from app.schemas.dispatch_health_failover import DispatchHealthCreate, DispatchHealthEvidence
from app.services.dispatch_health_failover import DispatchHealthFailoverService

def payload(**kw):
    data=dict(workspace_id="ws-a",source_key="health-1",requested_by="operator",dispatch_plan_id="plan-1",dispatch_plan_digest="12345678abcdef",operation="read-status",target="https://example.com/status",primary_adapter_id="adapter-a",primary_worker_id="worker-a",standby_adapter_id="adapter-b",standby_worker_id="worker-b",evidence=DispatchHealthEvidence(primary_available=True,latency_ms=100,receipt_reconciliation=1,worker_heartbeat_ok=True,gateway_healthy=True,adapter_healthy=True))
    data.update(kw); return DispatchHealthCreate(**data)

def test_healthy_evaluation():
    s=DispatchHealthFailoverService(); r=s.create(payload()); r=s.act("ws-a",r.record_id,"evaluate","reviewer","op-1"); assert r.state.value=="healthy"; assert not r.triggers

def test_latency_trigger_requires_approval_before_authorization():
    s=DispatchHealthFailoverService(); p=payload(evidence=DispatchHealthEvidence(primary_available=True,latency_ms=5000,receipt_reconciliation=1,worker_heartbeat_ok=True,gateway_healthy=True,adapter_healthy=True)); r=s.create(p); assert "latency-degraded" in r.triggers
    r=s.act("ws-a",r.record_id,"evaluate","reviewer","op-1"); assert r.state.value=="degraded"
    with pytest.raises(ValueError,match="approval required"): s.act("ws-a",r.record_id,"authorize-failover","owner","op-2")
    r=s.act("ws-a",r.record_id,"approve","owner","op-3"); r=s.act("ws-a",r.record_id,"authorize-failover","owner","op-4"); assert r.state.value=="failover-authorized"

def test_worker_and_gateway_triggers():
    s=DispatchHealthFailoverService(); p=payload(evidence=DispatchHealthEvidence(primary_available=True,latency_ms=100,receipt_reconciliation=1,worker_heartbeat_ok=False,gateway_healthy=False,adapter_healthy=True)); r=s.create(p); assert "worker-heartbeat-lost" in r.triggers; assert "gateway-unhealthy" in r.triggers

def test_protected_operation_hard_blocks():
    s=DispatchHealthFailoverService(); r=s.create(payload(operation="trade-execute")); assert r.state.value=="blocked"
    with pytest.raises(ValueError,match="hard block"): s.act("ws-a",r.record_id,"evaluate","reviewer","op-1")

def test_replay_and_isolation():
    s=DispatchHealthFailoverService(); r=s.create(payload()); s.act("ws-a",r.record_id,"evaluate","reviewer","same")
    with pytest.raises(ValueError,match="replay"): s.act("ws-a",r.record_id,"submit-review","reviewer","same")
    with pytest.raises(KeyError): s.get("ws-b",r.record_id)

def test_duplicate_source_rejected():
    s=DispatchHealthFailoverService(); s.create(payload())
    with pytest.raises(ValueError,match="duplicate source_key"): s.create(payload())
