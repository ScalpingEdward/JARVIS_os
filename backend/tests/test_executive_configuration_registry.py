from uuid import uuid4

import pytest

from app.executive_configuration_registry.models import ConfigurationAssessmentCreate, ConfigurationObservation, ConfigurationState, SecretReference
from app.executive_configuration_registry.service import ExecutiveConfigurationRegistryService


def valid_payload(**overrides):
    data = dict(
        workspace_id="ws-a",
        source_key="cfg-source-1",
        actor_id="operator",
        configuration_key="broker.mt5.primary",
        version=1,
        schema_version="1.0",
        scope="broker",
        environment="production",
        target_module="broker-connector",
        observation=ConfigurationObservation(
            secret_references=[SecretReference(name="broker-token", reference="vault://broker/token", resolved=True, scope_verified=True)]
        ),
    )
    data.update(overrides)
    return ConfigurationAssessmentCreate(**data)


def test_runtime_ready_configuration():
    service = ExecutiveConfigurationRegistryService()
    record = service.create(valid_payload())
    assert record.state == ConfigurationState.runtime_ready
    assert record.runtime_ready is True


def test_schema_invalid():
    service = ExecutiveConfigurationRegistryService()
    payload = valid_payload(observation=ConfigurationObservation(schema_registered=False))
    assert service.create(payload).state == ConfigurationState.schema_invalid


def test_secret_reference_missing():
    service = ExecutiveConfigurationRegistryService()
    payload = valid_payload(observation=ConfigurationObservation(secret_references=[SecretReference(name="x", reference="vault://x")]))
    assert service.create(payload).state == ConfigurationState.secret_reference_missing


def test_configuration_drift():
    service = ExecutiveConfigurationRegistryService()
    payload = valid_payload(observation=ConfigurationObservation(runtime_checksum_verified=False))
    assert service.create(payload).state == ConfigurationState.configuration_drift


def test_reload_required_for_rotation():
    service = ExecutiveConfigurationRegistryService()
    secret = SecretReference(name="x", reference="vault://x", resolved=True, scope_verified=True, rotation_due=True)
    payload = valid_payload(observation=ConfigurationObservation(secret_references=[secret]))
    assert service.create(payload).state == ConfigurationState.reload_required


def test_raw_secrets_blocked():
    service = ExecutiveConfigurationRegistryService()
    payload = valid_payload(observation=ConfigurationObservation(raw_secrets_present=True))
    assert service.create(payload).state == ConfigurationState.blocked


def test_risk_brain_blocks():
    service = ExecutiveConfigurationRegistryService()
    assert service.create(valid_payload(risk_brain_clear=False)).state == ConfigurationState.blocked


def test_duplicate_version_rejected():
    service = ExecutiveConfigurationRegistryService()
    first = valid_payload()
    second = valid_payload(source_key="cfg-source-2", configuration_id=uuid4())
    service.create(first)
    with pytest.raises(ValueError, match="Duplicate configuration key and version"):
        service.create(second)


def test_workspace_isolation():
    service = ExecutiveConfigurationRegistryService()
    record = service.create(valid_payload())
    assert service.get(record.id, "ws-b") is None
    assert service.list_configurations("ws-b") == []
