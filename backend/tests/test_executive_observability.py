from uuid import uuid4

from app.executive_observability.models import (
    ObservabilityAssessmentCreate,
    ObservabilityObservation,
    ObservabilityState,
    SpanKind,
    SpanObservation,
)
from app.executive_observability.service import ExecutiveObservabilityService


def valid_payload(workspace_id: str = "ws-1") -> ObservabilityAssessmentCreate:
    return ObservabilityAssessmentCreate(
        workspace_id=workspace_id,
        source_key="trace-source-1",
        actor_id="tester",
        executor_transport_assessment_id="transport-1",
        executor_transport_state="dispatched",
        trace_id="0123456789abcdef0123456789abcdef",
        correlation_id="corr-12345678",
        workflow_instance_id=uuid4(),
        observation=ObservabilityObservation(
            trace_created=True,
            trace_context_propagated=True,
            correlation_id_propagated=True,
            opentelemetry_compatible=True,
            structured_logs_emitted=True,
            metrics_emitted=True,
            metrics_exporter_verified=True,
            trace_exporter_verified=True,
            audit_linked=True,
            error_attribution_verified=True,
            total_operations=100,
            failed_operations=1,
            spans=[
                SpanObservation(
                    span_id="span0001",
                    kind=SpanKind.workflow,
                    component="workflow",
                    started=True,
                    completed=True,
                    status_recorded=True,
                    attributes_sanitized=True,
                ),
                SpanObservation(
                    span_id="span0002",
                    parent_span_id="span0001",
                    kind=SpanKind.transport,
                    component="transport",
                    started=True,
                    completed=True,
                    status_recorded=True,
                    attributes_sanitized=True,
                ),
            ],
        ),
    )


def test_accepts_healthy_observability() -> None:
    result = ExecutiveObservabilityService().create(valid_payload())
    assert result.state == ObservabilityState.healthy
    assert result.healthy is True


def test_requires_trace_context() -> None:
    payload = valid_payload()
    payload.observation.trace_context_propagated = False
    assert ExecutiveObservabilityService().create(payload).state == ObservabilityState.trace_required


def test_degrades_missing_metrics_exporter() -> None:
    payload = valid_payload()
    payload.observation.metrics_exporter_verified = False
    assert ExecutiveObservabilityService().create(payload).state == ObservabilityState.metrics_degraded


def test_detects_budget_breach() -> None:
    payload = valid_payload()
    payload.observation.transport_latency_ms = 20_001
    assert ExecutiveObservabilityService().create(payload).state == ObservabilityState.budget_exceeded


def test_warns_on_failure_rate() -> None:
    payload = valid_payload()
    payload.observation.failed_operations = 3
    assert ExecutiveObservabilityService().create(payload).state == ObservabilityState.warning


def test_blocks_raw_secrets() -> None:
    payload = valid_payload()
    payload.observation.raw_secrets_present = True
    assert ExecutiveObservabilityService().create(payload).state == ObservabilityState.blocked


def test_risk_brain_blocks() -> None:
    payload = valid_payload()
    payload.risk_brain_clear = False
    assert ExecutiveObservabilityService().create(payload).state == ObservabilityState.blocked


def test_duplicate_trace_rejected() -> None:
    service = ExecutiveObservabilityService()
    first = valid_payload()
    service.create(first)
    second = valid_payload()
    second.source_key = "trace-source-2"
    second.trace_id = first.trace_id
    try:
        service.create(second)
    except ValueError as exc:
        assert "Duplicate trace ID" in str(exc)
    else:
        raise AssertionError("duplicate trace was accepted")


def test_workspace_isolation() -> None:
    service = ExecutiveObservabilityService()
    record = service.create(valid_payload())
    assert service.get(record.id, "other") is None
