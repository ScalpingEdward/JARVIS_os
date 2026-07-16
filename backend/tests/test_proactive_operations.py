from fastapi.testclient import TestClient

from app.main import app
from app.proactive_operations.service import proactive_operations_service


client = TestClient(app)


def setup_function() -> None:
    proactive_operations_service.reset()


def test_prioritizes_critical_human_gated_event() -> None:
    response = client.post(
        "/v1/proactive-operations/events",
        json={
            "source": "trade-analyst",
            "domain": "trading",
            "title": "XAUUSD risk limit reached",
            "summary": "New positions should remain blocked pending review.",
            "severity": "critical",
            "confidence": 0.95,
            "urgency": 1.0,
            "impact": 1.0,
            "requires_human_approval": True,
            "deduplication_key": "xau-risk-limit",
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["priority_score"] >= 90
    assert "MASTER Brano" in body["executive_message"]
    assert body["requires_human_approval"] is True


def test_suppresses_open_duplicate() -> None:
    payload = {
        "source": "system",
        "domain": "system",
        "title": "Connector degraded",
        "summary": "MT5 heartbeat is delayed.",
        "severity": "high",
        "deduplication_key": "mt5-degraded",
    }
    first = client.post("/v1/proactive-operations/events", json=payload).json()
    second = client.post("/v1/proactive-operations/events", json=payload).json()
    assert first["id"] == second["id"]
    status = client.get("/v1/proactive-operations/status").json()
    assert status["suppressed_duplicates"] == 1
    assert status["automatic_execution"] is False
    assert status["automatic_order_execution"] is False


def test_alert_status_requires_explicit_update() -> None:
    created = client.post(
        "/v1/proactive-operations/events",
        json={
            "source": "research",
            "domain": "research",
            "title": "Macro event approaching",
            "summary": "High-impact release is scheduled soon.",
            "severity": "medium",
        },
    ).json()
    response = client.patch(
        f"/v1/proactive-operations/alerts/{created['id']}/status",
        json={"status": "acknowledged"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "acknowledged"
