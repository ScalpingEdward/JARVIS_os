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
from app.notification_hub.telegram_delivery import TelegramDeliveryError


@pytest.fixture(autouse=True)
def _reset_shared_state():
    """Storage is now real and shared rather than fresh-per-instance
    in-memory -- see AutomationRuntimeService's own docstring. Tests in
    this file reuse fixed connector_key/idempotency_key values across
    each other, so each test needs a clean slate."""
    AutomationRuntimeService().reset()
    yield


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
    # activate_connector() now returns a freshly-deserialized copy
    # (correct encapsulation, backed by real persistence -- see
    # AutomationRuntimeService's own docstring), not a live reference
    # into shared state the old in-memory dict implementation
    # accidentally allowed. Use its own return value, not the stale
    # reference from register_connector() above.
    return service.activate_connector(
        connector.id,
        "phoenix-main",
        "owner-1",
        ConnectorMutation(reason="approved"),
    )


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


# -- real (non-dry-run) execution: telegram only, everything else stays dry-run --


class FakeTelegramClient:
    """Records calls instead of touching the network -- see
    test_notification_hub_telegram.py for the real wire-format tests this
    module does not need to repeat."""

    def __init__(self, raises: TelegramDeliveryError | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self._raises = raises

    def send(self, title: str, message: str) -> None:
        self.calls.append((title, message))
        if self._raises:
            raise self._raises


def telegram_connector_payload(**overrides):
    values = {
        "connector_key": "telegram.brano",
        "connector_type": ConnectorType.TELEGRAM,
        "display_name": "Telegram (Brano)",
        "capabilities": ["messaging.send"],
        "actions": ["send_message"],
    }
    values.update(overrides)
    return connector_payload(**values)


def real_job_payload(connector_id, **overrides):
    values = {"action": "send_message", "dry_run": False, "external_action": True,
              "payload": {"title": "Alert", "message": "Setup approved"}}
    values.update(overrides)
    return job_payload(connector_id, **values)


def test_a_real_job_is_refused_for_a_non_telegram_connector() -> None:
    service = AutomationRuntimeService()
    connector = active_connector(service)  # Instagram, from connector_payload()'s default
    job = service.create_job(real_job_payload(connector.id, action="preview_post", human_approved=True))
    assert job.state == JobState.BLOCKED
    assert "telegram" in job.blocked_reason.lower()
    assert job.dry_run is False and job.external_action is True, "still recorded honestly, even though blocked"


def test_a_real_job_is_accepted_for_a_telegram_connector() -> None:
    service = AutomationRuntimeService()
    connector = service.register_connector(telegram_connector_payload())
    service.activate_connector(connector.id, "phoenix-main", "owner-1", ConnectorMutation())
    job = service.create_job(real_job_payload(connector.id, human_approved=True))
    assert job.state == JobState.READY
    assert job.dry_run is False and job.external_action is True


def test_dispatch_next_does_not_fabricate_a_result_for_a_real_job() -> None:
    """A real job's result must be empty after claiming -- nothing was
    validated or simulated, unlike the dry-run placeholder."""
    service = AutomationRuntimeService()
    connector = service.register_connector(telegram_connector_payload())
    service.activate_connector(connector.id, "phoenix-main", "owner-1", ConnectorMutation())
    service.create_job(real_job_payload(connector.id, human_approved=True))
    running = service.dispatch_next("phoenix-main")
    assert running.state == JobState.RUNNING
    assert running.result == {}


def test_execute_telegram_job_sends_and_completes() -> None:
    fake = FakeTelegramClient()
    service = AutomationRuntimeService(telegram_client=fake)
    connector = service.register_connector(telegram_connector_payload())
    service.activate_connector(connector.id, "phoenix-main", "owner-1", ConnectorMutation())
    job = service.create_job(real_job_payload(connector.id, human_approved=True))
    service.dispatch_next("phoenix-main")

    completed = service.execute_telegram_job(job.id, "phoenix-main")

    assert fake.calls == [("Alert", "Setup approved")]
    assert completed.state == JobState.COMPLETED
    assert completed.result["channel"] == "telegram"
    assert completed.result["external_side_effect"] is True, "a real send actually happened"


def test_a_dry_run_jobs_external_side_effect_stays_false() -> None:
    """Regression guard for the fix: complete_job() used to hardcode
    external_side_effect=False unconditionally, which happened to be
    correct for dry runs but would have been wrong once a real path
    existed. This confirms the derived value still comes out right for the
    ordinary case."""
    service = AutomationRuntimeService()
    connector = active_connector(service)
    job = service.create_job(job_payload(connector.id, human_approved=True))
    service.dispatch_next("phoenix-main")
    completed = service.complete_job(job.id, "phoenix-main", JobCompletion(success=True, result={}))
    assert completed.result["external_side_effect"] is False


def test_execute_telegram_job_reports_a_delivery_failure() -> None:
    fake = FakeTelegramClient(raises=TelegramDeliveryError("no bot token configured"))
    service = AutomationRuntimeService(telegram_client=fake)
    connector = service.register_connector(telegram_connector_payload())
    service.activate_connector(connector.id, "phoenix-main", "owner-1", ConnectorMutation())
    job = service.create_job(real_job_payload(connector.id, human_approved=True, max_retries=0))
    service.dispatch_next("phoenix-main")

    failed = service.execute_telegram_job(job.id, "phoenix-main")
    assert failed.state == JobState.FAILED
    assert "no bot token" in failed.error


def test_execute_telegram_job_refuses_a_job_that_is_not_running() -> None:
    fake = FakeTelegramClient()
    service = AutomationRuntimeService(telegram_client=fake)
    connector = service.register_connector(telegram_connector_payload())
    service.activate_connector(connector.id, "phoenix-main", "owner-1", ConnectorMutation())
    job = service.create_job(real_job_payload(connector.id, human_approved=True))
    # never dispatched -- still READY, not RUNNING
    with pytest.raises(ValueError, match="not running"):
        service.execute_telegram_job(job.id, "phoenix-main")
    assert fake.calls == []


def test_execute_telegram_job_refuses_an_ordinary_dry_run_job() -> None:
    """Defense in depth: even a RUNNING job must actually be a real,
    Telegram job -- a normal dry-run job that happens to be RUNNING must
    not be executable through this method."""
    fake = FakeTelegramClient()
    service = AutomationRuntimeService(telegram_client=fake)
    connector = service.register_connector(telegram_connector_payload())
    service.activate_connector(connector.id, "phoenix-main", "owner-1", ConnectorMutation())
    job = service.create_job(job_payload(connector.id, action="send_message", human_approved=True))
    service.dispatch_next("phoenix-main")
    with pytest.raises(ValueError, match="dry run"):
        service.execute_telegram_job(job.id, "phoenix-main")
    assert fake.calls == []


def test_runtime_status_names_telegram_as_the_one_real_connector() -> None:
    service = AutomationRuntimeService()
    status = service.status()
    assert status.real_execution_connector_types == ["telegram"]
    assert status.dry_run_only is False


def test_connectors_and_jobs_survive_a_fresh_service_instance():
    """The actual fix: a genuinely new instance (simulating a restart)
    sees exactly what a previous one registered, activated, and queued --
    including a job's idempotency key, still correctly deduplicating
    across the restart."""
    first = AutomationRuntimeService()
    connector = first.activate_connector(
        first.register_connector(connector_payload()).id, "phoenix-main", "owner-1",
        ConnectorMutation(reason="approved"),
    )
    job = first.create_job(AutomationJobCreate(
        workspace_id="phoenix-main", requester_id="brano", connector_id=connector.id,
        action="preview_post", payload={}, idempotency_key="restart-proof-key",
    ))

    second = AutomationRuntimeService()  # nothing shared but the real database
    restored_connector = second.get_connector(connector.id, "phoenix-main")
    assert restored_connector.state.value == "active"
    restored_job = second.get_job(job.id, "phoenix-main")
    assert restored_job is not None

    # idempotency must still work across the "restart"
    duplicate = second.create_job(AutomationJobCreate(
        workspace_id="phoenix-main", requester_id="brano", connector_id=connector.id,
        action="preview_post", payload={}, idempotency_key="restart-proof-key",
    ))
    assert duplicate.id == job.id
