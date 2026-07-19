from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(workspace_id: str = "remote-a") -> dict:
    return {
        "workspace_id": workspace_id,
        "name": "Digital services portfolio",
        "opportunities": [{
            "title": "Automation documentation contract",
            "source": "marketplace",
            "opportunity_type": "freelance",
            "compensation_eur": 1200,
            "estimated_hours": 20,
            "skill_fit": 90,
            "ai_automation_fit": 85,
            "delivery_confidence": 88,
            "client_quality": 80,
            "contract_clarity": 82,
            "delivery_mode": "ai_assisted",
            "ai_use_permitted": True
        }],
        "engagements": [{
            "name": "Existing client",
            "committed_hours": 10,
            "capacity_limit_hours": 40,
            "quality_score": 90,
            "deadline_readiness": 88,
            "margin_percent": 55,
            "client_satisfaction": 92
        }],
        "risks": [{
            "category": "payment",
            "description": "Milestone terms require verification",
            "severity": 60,
            "probability": 45,
            "impact": 70,
            "remediation_progress": 20
        }]
    }


def test_create_assess_and_update_remote_work_portfolio() -> None:
    created = client.post("/v1/executive-remote-work/portfolios", json=payload())
    assert created.status_code == 201
    item = created.json()
    assessed = client.post(f"/v1/executive-remote-work/portfolios/{item['portfolio_id']}/assess", params={"workspace_id": "remote-a", "actor_id": "master-brano"})
    assert assessed.status_code == 200
    body = assessed.json()
    assert body["opportunity_quality_score"] > 80
    assert body["ethical_readiness_score"] == 100
    assert len(body["priority_opportunity_ids"]) == 1
    risk_id = body["risks"][0]["risk_id"]
    updated = client.post(f"/v1/executive-remote-work/portfolios/{item['portfolio_id']}/risks", params={"workspace_id": "remote-a"}, json={"risk_id": risk_id, "remediation_progress": 90})
    assert updated.status_code == 200
    assert updated.json()["risks"][0]["remediation_progress"] == 90


def test_workspace_isolation_and_duplicate_protection() -> None:
    first = client.post("/v1/executive-remote-work/portfolios", json=payload("remote-b"))
    assert first.status_code == 201
    assert client.post("/v1/executive-remote-work/portfolios", json=payload("remote-b")).status_code == 409
    portfolio_id = first.json()["portfolio_id"]
    assert client.get(f"/v1/executive-remote-work/portfolios/{portfolio_id}", params={"workspace_id": "other"}).status_code == 404


def test_execution_safety_flags_are_disabled() -> None:
    response = client.get("/v1/executive-remote-work/status", params={"workspace_id": "safe"})
    assert response.status_code == 200
    body = response.json()
    assert body["autonomous_application_enabled"] is False
    assert body["autonomous_identity_representation_enabled"] is False
    assert body["autonomous_delivery_enabled"] is False
