from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.position_monitor.service import position_monitor_service

client = TestClient(app)


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
