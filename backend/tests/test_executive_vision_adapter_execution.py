import pytest

from app.executive_vision_adapter_execution.models import AdapterAttempt, AdapterExecutionAssessmentCreate, AdapterExecutionState
from app.executive_vision_adapter_execution.service import ExecutiveVisionAdapterExecutionService


def attempt(**overrides):
    data = dict(
        attempt_number=1,
        success=True,
        latency_ms=1200,
        response_bytes=120_000,
        estimated_cost_units=1.2,
        http_status=200,
        schema_valid=True,
        safety_clear=True,
        extraction_confidence=91,
    )
    data.update(overrides)
    return AdapterAttempt(**data)


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        source_key="source-1",
        actor_id="tester",
        routing_assessment_id="routing-1",
        routing_state="dispatched",
        provider_id="openai",
        adapter_id="openai-vision",
        image_sha256="a" * 64,
        credential_reference="secret://vision/openai",
        credential_resolved=True,
        request_payload_redacted=True,
        risk_brain_clear=True,
        attempts=[attempt()],
    )
    data.update(overrides)
    return AdapterExecutionAssessmentCreate(**data)


def test_successful_execution_dispatches_to_consensus():
    result = ExecutiveVisionAdapterExecutionService().create(payload())
    assert result.state == AdapterExecutionState.dispatched
    assert result.dispatchable is True
    assert result.target_module == "executive-vision-adapter-consensus"


def test_missing_isolated_credential_is_blocked():
    result = ExecutiveVisionAdapterExecutionService().create(payload(credential_reference=None, credential_resolved=False))
    assert result.state == AdapterExecutionState.credential_required
    assert result.dispatchable is False


def test_retryable_failure_schedules_bounded_retry():
    result = ExecutiveVisionAdapterExecutionService().create(
        payload(attempts=[attempt(success=False, retryable=True, timed_out=True, schema_valid=False, extraction_confidence=0)])
    )
    assert result.state == AdapterExecutionState.retry_scheduled


def test_non_retryable_failure_fails():
    result = ExecutiveVisionAdapterExecutionService().create(
        payload(attempts=[attempt(success=False, retryable=False, http_status=401, schema_valid=False, extraction_confidence=0)])
    )
    assert result.state == AdapterExecutionState.failed


def test_risk_brain_blocks_execution():
    result = ExecutiveVisionAdapterExecutionService().create(payload(risk_brain_clear=False))
    assert result.state == AdapterExecutionState.blocked


def test_duplicate_and_workspace_isolation():
    service = ExecutiveVisionAdapterExecutionService()
    first = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.get(first.id, "other") is None
    assert len(service.list_assessments("ws-1")) == 1
