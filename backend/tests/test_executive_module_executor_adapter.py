from uuid import uuid4

from app.executive_module_executor_adapter.models import (
    AdapterObservation,
    FailureClass,
    ModuleExecutorAssessmentCreate,
    ModuleExecutorState,
)
from app.executive_module_executor_adapter.service import ExecutiveModuleExecutorAdapterService


def valid_payload(workspace_id: str = "ws-1") -> ModuleExecutorAssessmentCreate:
    return ModuleExecutorAssessmentCreate(
        workspace_id=workspace_id,
        source_key="invoke-1",
        actor_id="tester",
        workflow_executor_assessment_id="executor-1",
        workflow_executor_state="dispatched",
        task_id=uuid4(),
        adapter_id="vision-consensus-adapter",
        adapter_version="1.0.0",
        target_module="executive-vision-adapter-consensus",
        input_schema="vision-input-v1",
        output_schema="vision-result-v1",
        observation=AdapterObservation(
            adapter_registered=True,
            adapter_enabled=True,
            module_match=True,
            version_compatible=True,
            input_schema_valid=True,
            output_schema_valid=True,
            sandbox_enabled=True,
            filesystem_isolated=True,
            network_policy_verified=True,
            environment_allowlist_verified=True,
            secret_references_isolated=True,
            invocation_attempted=True,
            invocation_completed=True,
            result_normalized=True,
            result_checkpoint_persisted=True,
        ),
    )


def test_dispatches_normalized_result() -> None:
    result = ExecutiveModuleExecutorAdapterService().create(valid_payload())
    assert result.state == ModuleExecutorState.dispatched
    assert result.dispatchable is True


def test_rejects_missing_adapter() -> None:
    payload = valid_payload()
    payload.observation.adapter_registered = False
    assert ExecutiveModuleExecutorAdapterService().create(payload).state == ModuleExecutorState.adapter_unavailable


def test_rejects_invalid_schema() -> None:
    payload = valid_payload()
    payload.observation.output_schema_valid = False
    assert ExecutiveModuleExecutorAdapterService().create(payload).state == ModuleExecutorState.schema_rejected


def test_rejects_unsafe_sandbox() -> None:
    payload = valid_payload()
    payload.observation.network_policy_verified = False
    assert ExecutiveModuleExecutorAdapterService().create(payload).state == ModuleExecutorState.sandbox_rejected


def test_detects_resource_excess() -> None:
    payload = valid_payload()
    payload.observation.memory_mb = 2048
    assert ExecutiveModuleExecutorAdapterService().create(payload).state == ModuleExecutorState.resource_exceeded


def test_classifies_retryable_failure() -> None:
    payload = valid_payload()
    payload.observation.failure_class = FailureClass.transient
    payload.observation.invocation_completed = False
    payload.observation.result_normalized = False
    payload.observation.result_checkpoint_persisted = False
    result = ExecutiveModuleExecutorAdapterService().create(payload)
    assert result.state == ModuleExecutorState.retryable_failure
    assert result.retryable is True


def test_blocks_unapproved_side_effect() -> None:
    payload = valid_payload()
    payload.observation.side_effects_detected = True
    assert ExecutiveModuleExecutorAdapterService().create(payload).state == ModuleExecutorState.blocked


def test_duplicate_invocation_rejected() -> None:
    service = ExecutiveModuleExecutorAdapterService()
    first = valid_payload()
    service.create(first)
    second = valid_payload()
    second.source_key = "invoke-2"
    second.invocation_id = first.invocation_id
    try:
        service.create(second)
    except ValueError as exc:
        assert "Duplicate module invocation" in str(exc)
    else:
        raise AssertionError("duplicate module invocation was accepted")


def test_workspace_isolation() -> None:
    service = ExecutiveModuleExecutorAdapterService()
    record = service.create(valid_payload())
    assert service.get(record.id, "other") is None
