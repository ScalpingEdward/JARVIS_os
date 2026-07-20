from uuid import uuid4

from app.executive_executor_transport_runtime.models import (
    ExecutorTransportAssessmentCreate,
    ExecutorTransportState,
    TransportKind,
    TransportObservation,
)
from app.executive_executor_transport_runtime.service import ExecutiveExecutorTransportRuntimeService


def valid_payload(workspace_id: str = "ws-1") -> ExecutorTransportAssessmentCreate:
    return ExecutorTransportAssessmentCreate(
        workspace_id=workspace_id,
        source_key="transport-1",
        actor_id="tester",
        module_executor_assessment_id="module-executor-1",
        module_executor_state="dispatched",
        invocation_id=uuid4(),
        transport_id="http-primary",
        transport_kind=TransportKind.http,
        target_module="executive-vision-adapter-consensus",
        endpoint_or_callable="https://internal.example/v1/invoke",
        protocol_version="1",
        credential_reference="secret://workspace/http-primary",
        observation=TransportObservation(
            endpoint_resolved=True,
            protocol_compatible=True,
            tls_verified=True,
            hostname_verified=True,
            credential_reference_resolved=True,
            credential_scope_verified=True,
            health_probe_verified=True,
            circuit_breaker_registered=True,
            request_serialization_verified=True,
            response_deserialization_verified=True,
            correlation_headers_verified=True,
            cancellation_propagation_verified=True,
            invocation_acknowledged=True,
        ),
    )


def test_dispatches_verified_http_transport() -> None:
    result = ExecutiveExecutorTransportRuntimeService().create(valid_payload())
    assert result.state == ExecutorTransportState.dispatched
    assert result.dispatchable is True


def test_python_requires_callable_resolution() -> None:
    payload = valid_payload()
    payload.transport_kind = TransportKind.python
    payload.endpoint_or_callable = "app.worker:invoke"
    payload.observation.endpoint_resolved = False
    payload.observation.callable_resolved = False
    assert ExecutiveExecutorTransportRuntimeService().create(payload).state == ExecutorTransportState.configuration_required


def test_rejects_raw_credentials() -> None:
    payload = valid_payload()
    payload.observation.raw_credentials_present = True
    assert ExecutiveExecutorTransportRuntimeService().create(payload).state == ExecutorTransportState.credential_rejected


def test_requires_tls_for_remote_transport() -> None:
    payload = valid_payload()
    payload.observation.tls_verified = False
    assert ExecutiveExecutorTransportRuntimeService().create(payload).state == ExecutorTransportState.transport_unavailable


def test_detects_open_circuit() -> None:
    payload = valid_payload()
    payload.observation.circuit_open = True
    assert ExecutiveExecutorTransportRuntimeService().create(payload).state == ExecutorTransportState.circuit_open


def test_detects_health_budget_degradation() -> None:
    payload = valid_payload()
    payload.observation.latency_ms = 20_001
    assert ExecutiveExecutorTransportRuntimeService().create(payload).state == ExecutorTransportState.health_degraded


def test_risk_brain_blocks() -> None:
    payload = valid_payload()
    payload.risk_brain_clear = False
    assert ExecutiveExecutorTransportRuntimeService().create(payload).state == ExecutorTransportState.blocked


def test_duplicate_invocation_rejected() -> None:
    service = ExecutiveExecutorTransportRuntimeService()
    first = valid_payload()
    service.create(first)
    second = valid_payload()
    second.source_key = "transport-2"
    second.invocation_id = first.invocation_id
    try:
        service.create(second)
    except ValueError as exc:
        assert "Duplicate executor transport invocation" in str(exc)
    else:
        raise AssertionError("duplicate transport invocation was accepted")


def test_workspace_isolation() -> None:
    service = ExecutiveExecutorTransportRuntimeService()
    record = service.create(valid_payload())
    assert service.get(record.id, "other") is None
