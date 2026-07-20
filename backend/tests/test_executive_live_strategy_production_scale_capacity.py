from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BASE = "/v1/executive-live-strategy-production-scale-capacity"


def payload(source_key: str, **overrides):
    data = {
        "workspace_id": "ws-production",
        "source_key": source_key,
        "actor_id": "human-operator",
        "strategy_id": "strategy-successor",
        "probation_state": "graduate",
        "approved_strategy_capital": 100000,
        "current_deployed_capital": 50000,
        "human_approved": True,
        "risk_brain_clear": True,
        "performance": {
            "live_trades": 80,
            "live_days": 45,
            "profit_factor": 1.35,
            "max_drawdown_share": 0.04,
            "capacity_utilization_share": 0.55,
            "slippage_bps": 8,
            "fill_quality_score": 90,
            "regime_coverage_score": 85,
            "operational_stability_score": 92,
            "concentration_share": 0.20,
            "active_incidents": 0,
        },
    }
    data.update(overrides)
    return data


def test_allows_one_controlled_production_scale_step():
    response = client.post(f"{BASE}/assessments", json=payload("prod-scale-1"))
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "scale-controlled"
    assert body["deployable"] is True
    assert body["incremental_capital"] == 15000


def test_holds_capacity_until_production_evidence_is_complete():
    item = payload("prod-scale-2")
    item["performance"]["live_trades"] = 20
    response = client.post(f"{BASE}/assessments", json=item)
    assert response.status_code == 201
    assert response.json()["state"] == "hold-capacity"
    assert response.json()["incremental_capital"] == 0


def test_reduces_exposure_when_capacity_or_concentration_is_exceeded():
    item = payload("prod-scale-3")
    item["performance"]["capacity_utilization_share"] = 0.95
    response = client.post(f"{BASE}/assessments", json=item)
    assert response.status_code == 201
    assert response.json()["state"] == "reduce-exposure"
    assert response.json()["deployable"] is False


def test_risk_brain_or_incident_blocks_scaling():
    response = client.post(f"{BASE}/assessments", json=payload("prod-scale-4", risk_brain_clear=False))
    assert response.status_code == 201
    assert response.json()["state"] == "blocked"


def test_human_approval_is_required_for_incremental_capital():
    response = client.post(f"{BASE}/assessments", json=payload("prod-scale-5", human_approved=False))
    assert response.status_code == 201
    assert response.json()["state"] == "scale-controlled"
    assert response.json()["deployable"] is False
    assert response.json()["incremental_capital"] == 0


def test_duplicate_source_key_is_rejected_per_workspace():
    first = client.post(f"{BASE}/assessments", json=payload("prod-scale-6"))
    second = client.post(f"{BASE}/assessments", json=payload("prod-scale-6"))
    assert first.status_code == 201
    assert second.status_code == 409


def test_workspace_isolation_for_get_and_audit():
    created = client.post(f"{BASE}/assessments", json=payload("prod-scale-7")).json()
    missing = client.get(f"{BASE}/assessments/{created['id']}", params={"workspace_id": "other"})
    audit = client.get(f"{BASE}/audit", params={"workspace_id": "ws-production"})
    assert missing.status_code == 404
    assert audit.status_code == 200
    assert any(row["assessment_id"] == created["id"] for row in audit.json())
