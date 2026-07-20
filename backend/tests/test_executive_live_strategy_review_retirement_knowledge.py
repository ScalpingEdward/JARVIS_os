from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BASE = "/v1/executive-live-strategy-review-retirement-knowledge"


def payload(source_key: str, **overrides):
    strategy = {
        "strategy_id": "live-alpha-1",
        "lifecycle_state": "promote",
        "consecutive_failed_reviews": 0,
        "active_incidents": 0,
        "unresolved_findings": 0,
        "evidence_items": 20,
        "evidence_completeness_score": 90,
        "reproducibility_score": 85,
        "documentation_score": 88,
        "operational_dependency_score": 30,
        "retirement_candidate": False,
    }
    strategy.update(overrides.pop("strategy", {}))
    body = {
        "workspace_id": "ws-review",
        "source_key": source_key,
        "actor_id": "master-brano",
        "human_approved": True,
        "risk_brain_clear": True,
        "strategy": strategy,
        "policy": {},
    }
    body.update(overrides)
    return body


def test_retain_strategy_when_governance_is_complete():
    response = client.post(f"{BASE}/assessments", json=payload("retain-1"))
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == "retain"
    assert data["deployable"] is True
    assert data["knowledge"]["preservation_score"] >= 70


def test_retire_and_preserve_requires_complete_knowledge():
    response = client.post(
        f"{BASE}/assessments",
        json=payload("retire-1", strategy={"lifecycle_state": "retire", "retirement_candidate": True}),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == "retire"
    assert data["recommended_action"] == "retire-and-preserve"


def test_incomplete_retirement_moves_to_archive_completion():
    response = client.post(
        f"{BASE}/assessments",
        json=payload(
            "archive-1",
            strategy={
                "lifecycle_state": "retire",
                "retirement_candidate": True,
                "documentation_score": 20,
            },
        ),
    )
    assert response.status_code == 201
    assert response.json()["state"] == "archive"


def test_risk_brain_blocks_review():
    response = client.post(f"{BASE}/assessments", json=payload("blocked-1", risk_brain_clear=False))
    assert response.status_code == 201
    assert response.json()["state"] == "blocked"
    assert response.json()["deployable"] is False


def test_human_approval_gate_and_workspace_isolation():
    response = client.post(f"{BASE}/assessments", json=payload("approval-1", human_approved=False))
    assert response.status_code == 201
    assessment_id = response.json()["id"]
    assert response.json()["deployable"] is False
    hidden = client.get(f"{BASE}/assessments/{assessment_id}", params={"workspace_id": "other"})
    assert hidden.status_code == 404


def test_duplicate_source_key_rejected():
    body = payload("duplicate-1")
    assert client.post(f"{BASE}/assessments", json=body).status_code == 201
    assert client.post(f"{BASE}/assessments", json=body).status_code == 409
