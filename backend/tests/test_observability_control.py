import pytest
from pydantic import ValidationError

from app.observability_control.models import (
    AlertCreate, ControlSwitchCreate, IncidentCreate, IncidentState, MetricCreate,
    OperatorMutation, Severity, SLOCreate, SwitchState, TraceCreate,
)
from app.observability_control.service import ObservabilityControlService


def test_metrics_traces_and_workspace_isolation():
    service = ObservabilityControlService()
    metric = service.add_metric(MetricCreate(workspace_id="w1", source_module="task-engine", name="queue.depth", value=4))
    trace = service.add_trace(TraceCreate(workspace_id="w1", trace_id="t1", span_id="s1", source_module="task-engine", operation="create_task", duration_ms=12))
    assert metric.value == 4
    assert trace.success is True
    assert service.list_metrics("w2") == []
    assert service.list_traces("w1", "t1")[0].span_id == "s1"
    with pytest.raises(ValueError):
        service.add_trace(TraceCreate(workspace_id="w1", trace_id="t2", span_id="s1", source_module="task-engine", operation="duplicate", duration_ms=1))


def test_incident_lifecycle_requires_owner():
    service = ObservabilityControlService()
    incident = service.create_incident(IncidentCreate(workspace_id="w1", owner_id="owner", source_module="integration-hub", title="Event backlog", severity=Severity.ERROR))
    assert service.mutate_incident(incident.id, "w1", OperatorMutation(requester_id="wrong"), IncidentState.ACKNOWLEDGED) is None
    acknowledged = service.mutate_incident(incident.id, "w1", OperatorMutation(requester_id="owner"), IncidentState.ACKNOWLEDGED)
    resolved = service.mutate_incident(incident.id, "w1", OperatorMutation(requester_id="owner"), IncidentState.RESOLVED)
    assert acknowledged is not None
    assert resolved is not None and resolved.state == IncidentState.RESOLVED


def test_slo_duplicates_and_planning_only_switch():
    service = ObservabilityControlService()
    payload = SLOCreate(workspace_id="w1", owner_id="owner", module_key="task-engine", name="availability", target_percent=99.9, window_minutes=60)
    service.create_slo(payload)
    with pytest.raises(ValueError):
        service.create_slo(payload)
    switch = service.create_switch(ControlSwitchCreate(workspace_id="w1", owner_id="owner", module_key="task-engine"))
    changed = service.set_switch(switch.id, "w1", OperatorMutation(requester_id="owner", reason="maintenance"), SwitchState.DISABLED)
    assert changed is not None
    assert changed.state == SwitchState.DISABLED
    assert changed.applied is False


def test_alert_and_status():
    service = ObservabilityControlService()
    service.create_alert(AlertCreate(workspace_id="w1", owner_id="owner", source_module="task-engine", title="High latency", severity=Severity.WARNING, condition="p95 > 500"))
    status = service.status()
    assert status.version == "8.9"
    assert status.alerts == 1
    assert status.autonomous_remediation_enabled is False
    assert status.real_shutdown_enabled is False


def test_safety_rejects_external_export_remediation_and_shutdown():
    with pytest.raises(ValidationError):
        MetricCreate(workspace_id="w1", source_module="task-engine", name="x", value=1, export_external=True)
    with pytest.raises(ValidationError):
        TraceCreate(workspace_id="w1", trace_id="t", span_id="s", source_module="task-engine", operation="x", duration_ms=1, capture_secrets=True)
    with pytest.raises(ValidationError):
        AlertCreate(workspace_id="w1", owner_id="owner", source_module="x", title="x", severity=Severity.ERROR, condition="x", automatic_external_notification=True)
    with pytest.raises(ValidationError):
        IncidentCreate(workspace_id="w1", owner_id="owner", source_module="x", title="x", severity=Severity.CRITICAL, autonomous_remediation=True)
    with pytest.raises(ValidationError):
        ControlSwitchCreate(workspace_id="w1", owner_id="owner", module_key="x", execute_shutdown=True)
