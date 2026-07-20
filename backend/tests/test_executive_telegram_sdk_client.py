import pytest

from app.executive_telegram_sdk_client.models import (
    TelegramSdkClientAssessmentCreate,
    TelegramSdkClientState,
    TelegramSdkRuntimeConfig,
)
from app.executive_telegram_sdk_client.service import ExecutiveTelegramSdkClientService


def config(**overrides):
    data = dict(
        transport_type="telethon",
        sdk_package="telethon",
        sdk_version="1.40.0",
        session_reference="secret://telegram/session",
        api_id_reference="secret://telegram/api-id",
        api_hash_reference="secret://telegram/api-hash",
        references_resolved=True,
        raw_secret_values_present=False,
        session_file_embedded=False,
        read_only_mode=True,
        dependency_installed=True,
        import_verified=True,
        client_factory_verified=True,
        timeout_seconds=20,
        connection_retries=3,
    )
    data.update(overrides)
    return TelegramSdkRuntimeConfig(**data)


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        source_key="source-1",
        actor_id="tester",
        transport_assessment_id="transport-1",
        transport_state="transport-ready",
        client_id="telegram-client-1",
        config=config(),
        risk_brain_clear=True,
    )
    data.update(overrides)
    return TelegramSdkClientAssessmentCreate(**data)


def test_verified_telethon_config_dispatches():
    result = ExecutiveTelegramSdkClientService().create(payload())
    assert result.state == TelegramSdkClientState.dispatched
    assert result.dispatchable is True
    assert result.target_module == "executive-telegram-transport"


def test_unresolved_secret_references_require_configuration():
    result = ExecutiveTelegramSdkClientService().create(
        payload(config=config(references_resolved=False))
    )
    assert result.state == TelegramSdkClientState.configuration_required
    assert result.dispatchable is False


def test_missing_dependency_is_unavailable():
    result = ExecutiveTelegramSdkClientService().create(
        payload(config=config(dependency_installed=False, import_verified=False))
    )
    assert result.state == TelegramSdkClientState.dependency_unavailable


def test_raw_secret_values_are_not_dispatchable():
    result = ExecutiveTelegramSdkClientService().create(
        payload(config=config(raw_secret_values_present=True))
    )
    assert result.state in {
        TelegramSdkClientState.configuration_required,
        TelegramSdkClientState.blocked,
    }
    assert result.dispatchable is False


def test_risk_brain_blocks_client_configuration():
    result = ExecutiveTelegramSdkClientService().create(payload(risk_brain_clear=False))
    assert result.state == TelegramSdkClientState.blocked


def test_duplicate_and_workspace_isolation():
    service = ExecutiveTelegramSdkClientService()
    first = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.get(first.id, "other") is None
    assert len(service.list_assessments("ws-1")) == 1
