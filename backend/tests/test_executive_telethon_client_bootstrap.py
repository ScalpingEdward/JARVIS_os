import pytest

from app.executive_telethon_client_bootstrap.models import (
    TelethonBootstrapAssessmentCreate,
    TelethonBootstrapObservation,
    TelethonBootstrapState,
)
from app.executive_telethon_client_bootstrap.service import ExecutiveTelethonClientBootstrapService


def payload(workspace_id: str = "ws-1", source_key: str = "src-1") -> TelethonBootstrapAssessmentCreate:
    return TelethonBootstrapAssessmentCreate(
        workspace_id=workspace_id,
        source_key=source_key,
        actor_id="tester",
        sdk_client_assessment_id="sdk-1",
        sdk_client_state="dispatched",
        client_id="telethon-main",
        session_reference=f"secret://telegram/{workspace_id}",
        session_reference_resolved=True,
        expected_account_id="acct-1",
        observed_account_id="acct-1",
        observation=TelethonBootstrapObservation(
            client_instantiated=True,
            session_loaded=True,
            connected=True,
            authorized=True,
            identity_verified=True,
            read_only_verified=True,
            dry_run_only=True,
            update_handler_registered=True,
            media_download_probe_succeeded=True,
        ),
    )


def test_successful_bootstrap_dispatch() -> None:
    record = ExecutiveTelethonClientBootstrapService().create(payload())
    assert record.state == TelethonBootstrapState.dispatched
    assert record.dispatchable is True
    assert record.target_module == "executive-telegram-transport"


def test_unresolved_session_requires_bootstrap() -> None:
    item = payload()
    item.session_reference_resolved = False
    record = ExecutiveTelethonClientBootstrapService().create(item)
    assert record.state == TelethonBootstrapState.bootstrap_required


def test_unauthorized_session_requires_authentication() -> None:
    item = payload()
    item.observation.authorized = False
    record = ExecutiveTelethonClientBootstrapService().create(item)
    assert record.state == TelethonBootstrapState.authentication_required


def test_write_capability_is_blocked() -> None:
    item = payload()
    item.observation.write_method_exposed = True
    record = ExecutiveTelethonClientBootstrapService().create(item)
    assert record.state == TelethonBootstrapState.blocked


def test_incomplete_dry_run_fails() -> None:
    item = payload()
    item.observation.media_download_probe_succeeded = False
    record = ExecutiveTelethonClientBootstrapService().create(item)
    assert record.state == TelethonBootstrapState.dry_run_failed


def test_risk_brain_blocks_bootstrap() -> None:
    item = payload()
    item.risk_brain_clear = False
    record = ExecutiveTelethonClientBootstrapService().create(item)
    assert record.state == TelethonBootstrapState.blocked


def test_duplicate_and_workspace_isolation() -> None:
    service = ExecutiveTelethonClientBootstrapService()
    first = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    second = service.create(payload(workspace_id="ws-2", source_key="src-1"))
    assert service.get(first.id, "ws-2") is None
    assert service.get(second.id, "ws-2") is not None
