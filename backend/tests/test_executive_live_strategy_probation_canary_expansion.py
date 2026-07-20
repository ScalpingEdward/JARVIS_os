from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BASE = "/v1/executive-live-strategy-probation-canary-expansion"


def payload(source_key: str, **overrides):
    data = {
        "workspace_id": "ws-1",
        "source_key": source_key,
        "actor_id": "master-brano",
        "strategy_id": "replacement-1",
        "succession_state": "succession-ready",
        "approved_succession_capital": 10000,
        "current_deployed_capital": 1000,
        "human_approved": True,
        "risk_brain_clear": True,
        "performance": {
            "live_trades": 30,
            "live_days": 15,
            "profit_factor": 1.3,
            "max_drawdown_share": 0.02,
            "slippage_bps": 5,
            "execution_error_rate": 0.005,
            "regime_coverage_score": 80,
            "operational_stability_score": 90,
            "incidents": 0,
        },
    }
    data.update(overrides)
    return data


def test_controlled_expansion_is_deployable_after_gates():
    response = client.post(f"{BASE}/assessments", json=payload("expand-1"))
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "expand-controlled"
    assert body["deployable"] is True
    assert body["incremental_capital"] > 0
    assert body["autonomous_actions_enabled"] is False


def test_canary_is_held_until_live_evidence_is_complete():
    item = payload("hold-1")
    item["performance"]["live_trades"] = 5
    response = client.post(f"{BASE}/assessments", json=item)
    assert response.status_code == 201
    assert response.json()["state"] == "hold-canary"
    assert response.json()["incremental_capital"] == 0


def test_failed_gate_extends_probation():
    item = payload("extend-1")
    item["performance"]["max_drawdown_share"] = 0.08
    response = client.post(f"{BASE}/assessments", json=item)
    assert response.status_code == 201
    assert response.json()["state"] == "extend-probation"


def test_risk_brain_or_incident_blocks_expansion():
    item = payload("blocked-1", risk_brain_clear=False)
    response = client.post(f"{BASE}/assessments", json=item)
    assert response.status_code == 201
    assert response.json()["state"] == "blocked"
    assert response.json()["deployable"] is False


def test_human_approval_is_required():
    response = client.post(f"{BASE}/assessments", json=payload("approval-1", human_approved=False))
    assert response.status_code == 201
    assert response.json()["deployable"] is False
    assert response.json()["incremental_capital"] == 0


def test_duplicate_source_key_is_rejected_per_workspace():
    assert client.post(f"{BASE}/assessments", json=payload("duplicate-1")).status_code == 201
    assert client.post(f"{BASE}/assessments", json=payload("duplicate-1")).status_code == 409


def test_workspace_isolation_and_audit():
    created = client.post(f"{BASE}/assessments", json=payload("isolation-1")).json()
    assert client.get(f"{BASE}/assessments/{created['id']}?workspace_id=other").status_code == 404
    audit = client.get(f"{BASE}/audit?workspace_id=ws-1")
    assert audit.status_code == 200
    assert any(row["assessment_id"] == created["id"] for row in audit.json())
