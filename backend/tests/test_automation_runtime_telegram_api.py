"""API-level test for the one new route this session added to
automation_runtime -- the rest of the module is tested at the service
layer only, matching this module's own existing convention
(test_automation_runtime.py); this file exists because the new route's
FastAPI wiring (status codes, path) deserves its own real check the way
the equivalent Telegram routes elsewhere in this session got."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.automation_runtime.api as automation_api
from app.automation_runtime.models import ConnectorMutation, ConnectorType
from app.automation_runtime.service import AutomationRuntimeService
from app.main import app


@pytest.fixture(autouse=True)
def _reset_shared_state():
    """Storage is now real and shared rather than fresh-per-instance
    in-memory -- see AutomationRuntimeService's own docstring."""
    AutomationRuntimeService().reset()
    yield
from tests.test_automation_runtime import (
    FakeTelegramClient,
    real_job_payload,
    telegram_connector_payload,
)

client = TestClient(app)


def _service_with_fake(fake: FakeTelegramClient) -> AutomationRuntimeService:
    service = AutomationRuntimeService(telegram_client=fake)
    connector = service.register_connector(telegram_connector_payload())
    service.activate_connector(connector.id, "phoenix-main", "owner-1", ConnectorMutation())
    return service, connector


def test_execute_telegram_endpoint_sends_for_real(monkeypatch):
    fake = FakeTelegramClient()
    service, connector = _service_with_fake(fake)
    job = service.create_job(real_job_payload(connector.id, human_approved=True))
    service.dispatch_next("phoenix-main")
    monkeypatch.setattr(automation_api, "automation_runtime_service", service)

    resp = client.post(f"/v1/automation-runtime/jobs/{job.id}/execute-telegram",
                       params={"workspace_id": "phoenix-main"})
    assert resp.status_code == 200
    assert resp.json()["result"]["external_side_effect"] is True
    assert fake.calls == [("Alert", "Setup approved")]


def test_execute_telegram_endpoint_404_for_unknown_job(monkeypatch):
    fake = FakeTelegramClient()
    service, _ = _service_with_fake(fake)
    monkeypatch.setattr(automation_api, "automation_runtime_service", service)

    import uuid
    resp = client.post(f"/v1/automation-runtime/jobs/{uuid.uuid4()}/execute-telegram",
                       params={"workspace_id": "phoenix-main"})
    assert resp.status_code == 404


def test_execute_telegram_endpoint_409_for_a_job_not_running(monkeypatch):
    fake = FakeTelegramClient()
    service, connector = _service_with_fake(fake)
    job = service.create_job(real_job_payload(connector.id, human_approved=True))
    monkeypatch.setattr(automation_api, "automation_runtime_service", service)

    resp = client.post(f"/v1/automation-runtime/jobs/{job.id}/execute-telegram",
                       params={"workspace_id": "phoenix-main"})
    assert resp.status_code == 409
    assert fake.calls == []
