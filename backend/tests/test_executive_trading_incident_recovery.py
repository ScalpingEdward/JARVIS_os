from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(source_key: str, **overrides):
    data = {
        "workspace_id": "ws-a",
        "actor_id": "ops",
        "source_key": source_key,
        "symbol": "XAUUSD",
        "account_profile": "ftmo-100k",
        "readiness_state": "blocked",
        "trading_decision": "freeze",
        "risk_state": "frozen",
        "rollback_available": False,
        "failover_available": False,
        "restart_safe": False,
        "data_integrity_score": 95,
        "recovery_confidence": 70,
        "incidents": [{
            "code": "FEED_DOWN",
            "component": "feed",
            "severity": "critical",
            "message": "Primary market feed unavailable",
            "blocking": True,
            "recurrence_count": 1,
            "age_minutes": 2,
        }],
    }
    data.update(overrides)
    return data


def test_critical_incident_is_contained_and_blocked():
    response = client.post("/v1/executive-trading-incident-recovery/assessments", json=payload("critical-1"))
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "contained"
    assert body["plan"]["primary_action"] == "isolate"
    assert body["trading_blocked"] is True


def test_failover_is_selected_when_available():
    response = client.post(
        "/v1/executive-trading-incident-recovery/assessments",
        json=payload("failover-1", failover_available=True),
    )
    assert response.status_code == 201
    assert response.json()["plan"]["primary_action"] == "failover"


def test_recurrent_incident_prefers_rollback():
    incidents = [{
        "code": "PARSER_LOOP",
        "component": "parser",
        "severity": "high",
        "message": "Parser repeatedly enters an error loop",
        "blocking": True,
        "recurrence_count": 3,
        "age_minutes": 20,
    }]
    response = client.post(
        "/v1/executive-trading-incident-recovery/assessments",
        json=payload("rollback-1", incidents=incidents, rollback_available=True),
    )
    assert response.status_code == 201
    assert response.json()["plan"]["primary_action"] == "rollback"


def test_low_data_integrity_forces_manual_block():
    response = client.post(
        "/v1/executive-trading-incident-recovery/assessments",
        json=payload("integrity-1", data_integrity_score=40, failover_available=True),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "blocked"
    assert body["plan"]["primary_action"] == "remain_blocked"


def test_workspace_isolation_and_duplicate_protection():
    assert client.post("/v1/executive-trading-incident-recovery/assessments", json=payload("isolation-1")).status_code == 201
    assert client.post("/v1/executive-trading-incident-recovery/assessments", json=payload("isolation-1")).status_code == 409
    other = payload("isolation-1", workspace_id="ws-b")
    assert client.post("/v1/executive-trading-incident-recovery/assessments", json=other).status_code == 201
    listed = client.get("/v1/executive-trading-incident-recovery/assessments", params={"workspace_id": "ws-a"})
    assert listed.status_code == 200
    assert all(item["workspace_id"] == "ws-a" for item in listed.json()["items"])
