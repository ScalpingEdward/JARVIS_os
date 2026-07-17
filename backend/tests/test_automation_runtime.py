import pytest
from pydantic import ValidationError

from app.automation_runtime.models import (
    AutomationJobCreate,
    ConnectorMutation,
    ConnectorRegister,
    ConnectorType,
    JobApproval,
    JobCompletion,
    JobState,
)
from app.automation_runtime.service import AutomationRuntimeService


def connector_payload(**overrides) -> ConnectorRegister:
    values = {
        "workspace_id": "phoenix-main",
        "owner_id": "owner-1",
        "connector_key": "instagram.main",
        "connector_type": ConnectorType.INSTAGRAM,
        "display_name": "Instagram Main",
        "capabilities": ["social.read", "social.compose"],
        "actions": ["preview_post", "validate_caption"],
        "rate_limit_per_minute": 2,
        "supports_dry_run": True,
    }
    values.update(overrides)
    return ConnectorRegister(**values)


def job_payload(connector_id, **overrides) -> AutomationJobCreate:
    values = {
        "workspace_id": "phoenix-main",
        "requester_id": "owner-1",
        "connector_id": connector_id,
        "action": "preview_post",
        "payload": {"caption": "test"},
        "idempotency_key": "job-001",
        "dry_run": True,
        "requires_human_approval": True,
        "human_approved": False,
    }
    values.update(overrides)
    return AutomationJobCreate(**values)


def active_connector(service: AutomationRuntimeService):
    connector = service.register_connector(connector_payload())
    service.activate_connector(
        connector.id,
        "phoenix-main",
        "owner-1",
        ConnectorMutation(reason="approved"),
    )
    return connector


def test_connector_registration_activation_and_workspace_isolation() -> None:
    service = AutomationRuntimeService()
    connector = active_connector(service)
    assert connector.state.value == "active"
    assert service.get_connector(connector.id, "other-workspace") is None
    assert service.list_connectors("phoenix-main") == [connector]


def test_job_waits_for_approval_then_runs_as_dry_run() -> None:
    service = AutomationRuntimeService()
    connector = active_connector(service)
    job = service.create_job(job_payload(connector.id))
    assert job.state == JobState.WAITING_APPROVAL
    approved = service.approve_job(job.id, "phoenix-main", JobApproval(approved=True, approved_by="owner-1"))
    assert approved is not None and approved.state == JobState.READY
    running = service.dispatch_next("phoenix-main")
    assert running is not None and running.state == JobState.RUNNING
    assert running.result["mode"] == "dry_run"
    completed = service.complete_job(
        running.id,
        "phoenix-main",
        JobCompletion(success=True, result={"preview_url": "local://preview"}),
    )
    assert completed is not None and completed.state == JobState.COMPLETED
    assert completed.result["external_side_effect"] is False


def test_idempotency_returns_original_job() -> None:
    service = AutomationRuntimeService()
    connector = active_connector(service)
    first = service.create_job(job_payload(connector.id, human_approved=True))
    second = service.create_job(job_payload(connector.id, human_approved=True, payload={"caption": "changed"}))
    assert first.id == second.id
    assert second.payload == {"caption": "test"}


def test_unknown_action_and_inactive_connector_are_blocked() -> None:
    service = AutomationRuntimeService()
    connector = service.register_connector(connector_payload())
    inactive = service.create_job(job_payload(connector.id, idempotency_key="inactive", human_approved=True))
    assert inactive.state == JobState.BLOCKED
    service.activate_connector(connector.id, "phoenix-main", "owner-1", ConnectorMutation(reason="active"))
    unknown = service.create_job(
        job_payload(connector.id, idempotency_key="unknown", action="publish_post", human_approved=True)
    )
    assert unknown.state == JobState.BLOCKED


def test_retry_then_failure() -> None:
    service = AutomationRuntimeService()
    connector = active_connector(service)
    job = service.create_job(job_payload(connector.id, human_approved=True, max_retries=1))
    service.dispatch_next("phoenix-main")
    retried = service.complete_job(job.id, "phoenix-main", JobCompletion(success=False, error="timeout"))
    assert retried is not None and retried.state == JobState.READY
    service.dispatch_next("phoenix-main")
    failed = service.complete_job(job.id, "phoenix-main", JobCompletion(success=False, error="timeout"))
    assert failed is not None and failed.state == JobState.FAILED


def test_rate_limit_prevents_extra_dispatch_in_window() -> None:
    service = AutomationRuntimeService()
    connector = active_connector(service)
    jobs = [
        service.create_job(
            job_payload(connector.id, idempotency_key=f"rate-{index}", human_approved=True)
        )
        for index in range(3)
    ]
    assert service.dispatch_next("phoenix-main") is not None
    assert service.dispatch_next("phoenix-main") is not None
    assert service.dispatch_next("phoenix-main") is None
    assert jobs[2].state == JobState.READY


def test_external_or_non_dry_run_jobs_are_rejected() -> None:
    service = AutomationRuntimeService()
    connector = active_connector(service)
    with pytest.raises(ValidationError):
        job_payload(connector.id, external_action=True)
    with pytest.raises(ValidationError):
        job_payload(connector.id, dry_run=False)
    with pytest.raises(ValidationError):
        connector_payload(human_approved=False)
