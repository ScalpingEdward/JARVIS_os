from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BASE = "/v1/executive-live-strategy-succession-replacement"


def payload(source_key: str, **overrides):
    data = {
        "workspace_id": "ws-a",
        "source_key": source_key,
        "actor_id": "master-brano",
        "retired_strategy_id": "legacy-xau",
        "retirement_state": "retire",
        "released_capital": 10000,
        "human_approved": True,
        "risk_brain_clear": True,
        "archive_complete": True,
        "candidate": {
            "strategy_id": "successor-xau",
            "evidence_trades": 60,
            "profit_factor": 1.45,
            "max_drawdown_share": 0.05,
            "regime_fit_score": 82,
            "execution_quality_score": 88,
            "correlation_to_retired_strategy": 0.35,
            "operational_readiness_score": 90,
        },
        "policy": {},
    }
    data.update(overrides)
    return data


def test_succession_ready_with_controlled_capital():
    response = client.post(f"{BASE}/assessments", json=payload("ready-1"))
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "succession-ready"
    assert body["deployable"] is True
    assert body["approved_capital"] == 2500


def test_missing_archive_preserves_capital():
    response = client.post(f"{BASE}/assessments", json=payload("archive-1", archive_complete=False))
    assert response.status_code == 201
    assert response.json()["state"] == "preserve-capital"
    assert response.json()["approved_capital"] == 0


def test_small_sample_observes_candidate():
    data = payload("observe-1")
    data["candidate"]["evidence_trades"] = 10
    response = client.post(f"{BASE}/assessments", json=data)
    assert response.status_code == 201
    assert response.json()["state"] == "observe-candidate"


def test_risk_brain_blocks_succession():
    response = client.post(f"{BASE}/assessments", json=payload("blocked-1", risk_brain_clear=False))
    assert response.status_code == 201
    assert response.json()["state"] == "blocked"
    assert response.json()["deployable"] is False


def test_human_approval_required():
    response = client.post(f"{BASE}/assessments", json=payload("approval-1", human_approved=False))
    assert response.status_code == 201
    assert response.json()["state"] == "succession-ready"
    assert response.json()["deployable"] is False


def test_duplicate_and_workspace_isolation():
    assert client.post(f"{BASE}/assessments", json=payload("duplicate-1")).status_code == 201
    assert client.post(f"{BASE}/assessments", json=payload("duplicate-1")).status_code == 409
    isolated = payload("duplicate-1", workspace_id="ws-b")
    assert client.post(f"{BASE}/assessments", json=isolated).status_code == 201
    assert len(client.get(f"{BASE}/assessments", params={"workspace_id": "ws-b"}).json()) == 1
