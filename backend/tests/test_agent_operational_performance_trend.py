import pytest
from app.schemas.agent_operational_performance_trend import OperationalTrendCreate
from app.services.agent_operational_performance_trend import AgentOperationalPerformanceTrendService

def payload(**overrides):
    o={"agent_id":"phoenix-agent","agent_version":"21.109","window_id":"30d","availability_trend":.98,"latency_trend":.98,"error_rate_trend":.98,"throughput_trend":.98,"business_kpi_trend":.98,"cost_efficiency":.95,"resource_efficiency":.95,"dependency_health":.98,"alert_quality":.95,"slo_posture":.98,"error_budget_posture":.98,"confidence":1.,"freshness":1.,"criticality":.7};o.update(overrides);return OperationalTrendCreate(workspace_id="ws-a",source_key="trend-source",requested_by="operator",observations=[o])
def test_status_disables_execution():
    s=AgentOperationalPerformanceTrendService().status();assert s["version"]=="21.109";assert s["automatic_tuning_enabled"] is False;assert s["autoscaling_enabled"] is False;assert s["trading_execution_enabled"] is False
def test_healthy_can_be_approved():
    s=AgentOperationalPerformanceTrendService();r=s.create(payload());assert not r.risk_flags;r=s.act("ws-a",r.record_id,"approve","owner","op-1");assert r.approved_by=="owner"
def test_degradation_blocks_approval():
    s=AgentOperationalPerformanceTrendService();r=s.create(payload(availability_trend=.4,sustained_degradation_events=1));assert any(x.startswith("performance-alert") for x in r.risk_flags)
    with pytest.raises(ValueError,match="findings block approval"):s.act("ws-a",r.record_id,"approve","owner","op-a")
def test_critical_degradation_hard_blocks():
    s=AgentOperationalPerformanceTrendService();r=s.create(payload(criticality=.98,availability_trend=.05,latency_trend=.05,error_rate_trend=.05,sustained_degradation_events=3));assert "risk-brain-hard-block" in r.risk_flags;assert r.state.value=="blocked"
def test_replay_and_isolation():
    s=AgentOperationalPerformanceTrendService();r=s.create(payload());s.act("ws-a",r.record_id,"assess","reviewer","same")
    with pytest.raises(ValueError,match="replay"):s.act("ws-a",r.record_id,"submit-review","reviewer","same")
    with pytest.raises(KeyError):s.get("ws-b",r.record_id)
def test_duplicate_source_rejected():
    s=AgentOperationalPerformanceTrendService();s.create(payload())
    with pytest.raises(ValueError,match="duplicate source_key"):s.create(payload())
