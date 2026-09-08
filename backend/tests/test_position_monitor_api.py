from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.position_monitor.service import position_monitor_service

# A plain TestClient(app) can open a fresh async context per call, which
# does not reliably preserve an asyncio.create_task() background task
# across separate .post() calls -- fine for every other test file in this
# suite (nothing else needs a task to survive between requests), but this
# file specifically tests a background loop staying alive across pause/
# resume calls, so it needs the one persistent context `with` gives.
_client_cm = TestClient(app)
client = _client_cm.__enter__()


def test_status_endpoint_is_off_by_default():
    """Confirms the actual production default, through the real app --
    not just the service's own constructor default."""
    resp = client.get("/v1/position-monitor/status")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_manual_tick_endpoint_runs_one_pass():
    resp = client.post("/v1/position-monitor/tick")
    assert resp.status_code == 200
    body = resp.json()
    assert "assessed" in body and "skipped" in body
    assert position_monitor_service.status().ticks_run >= 1


@pytest.fixture(autouse=True)
def _ensure_paused_before_and_after():
    """The monitor is a module-level singleton shared across every test in
    this file (and the whole app) -- a loop left running by one test would
    otherwise leak into the next. Pausing is a safe no-op when already
    stopped, so this costs nothing when a test never started anything."""
    client.post("/v1/position-monitor/pause")
    yield
    client.post("/v1/position-monitor/pause")


def test_pause_stops_a_running_loop():
    client.post("/v1/position-monitor/resume", json={"interval_seconds": 0.05})
    resp = client.post("/v1/position-monitor/pause")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert position_monitor_service._task is None


def test_pause_when_already_stopped_is_a_safe_no_op():
    """An operator reaching for the kill switch should never have to
    check first whether it's already off."""
    resp = client.post("/v1/position-monitor/pause")
    assert resp.status_code == 200
    resp2 = client.post("/v1/position-monitor/pause")
    assert resp2.status_code == 200
    assert resp2.json()["enabled"] is False


def test_resume_starts_the_loop_with_the_default_interval():
    resp = client.post("/v1/position-monitor/resume")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


def test_resume_with_an_explicit_interval_uses_it():
    resp = client.post("/v1/position-monitor/resume", json={"interval_seconds": 5})
    assert resp.status_code == 200
    assert resp.json()["interval_seconds"] == 5


def test_resume_without_a_body_keeps_the_previously_configured_interval():
    """Resuming must not silently reset an operator's earlier choice back
    to the module's own hardcoded default."""
    client.post("/v1/position-monitor/resume", json={"interval_seconds": 7})
    client.post("/v1/position-monitor/pause")
    resp = client.post("/v1/position-monitor/resume")  # no body this time
    assert resp.json()["interval_seconds"] == 7


def test_resume_when_already_running_is_a_safe_no_op():
    client.post("/v1/position-monitor/resume", json={"interval_seconds": 5})
    resp = client.post("/v1/position-monitor/resume", json={"interval_seconds": 99})
    # the second call must not spawn a competing task or change the interval
    # of the one already running
    assert resp.json()["interval_seconds"] == 5


def test_audit_endpoint_lists_notable_events():
    resp = client.post("/v1/position-monitor/tick")
    resp2 = client.get("/v1/position-monitor/audit")
    assert resp2.status_code == 200
    assert isinstance(resp2.json(), list)


def test_audit_endpoint_respects_limit():
    resp = client.get("/v1/position-monitor/audit", params={"limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()) <= 1
