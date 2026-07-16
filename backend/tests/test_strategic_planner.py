from fastapi.testclient import TestClient

from app.main import app
from app.strategic_planner.service import strategic_planner_service

client = TestClient(app)


def setup_function() -> None:
    strategic_planner_service.reset()


def test_plan_lifecycle_and_progress() -> None:
    response = client.post(
        "/v1/strategic-plans",
        json={
            "title": "Build sustainable trading business",
            "objective": "Reach stable profitability with controlled risk and verified systems.",
            "domain": "trading",
            "priority": 1,
            "milestones": [
                {"title": "Validate strategy", "priority": 1, "success_metrics": {"trades": 100}},
                {"title": "Scale capital", "priority": 2, "dependencies": ["Validate strategy"]},
            ],
            "risks": [{"name": "Excess drawdown", "probability": 0.3, "impact": 0.9, "mitigation": "Hard risk limits"}],
        },
    )
    assert response.status_code == 201
    plan = response.json()
    assert plan["state"] == "draft"
    assert plan["automatic_execution"] if "automatic_execution" in plan else True

    activated = client.post(f"/v1/strategic-plans/{plan['id']}/activate", json={"approved_by": "Brano"})
    assert activated.status_code == 200
    assert activated.json()["state"] == "active"

    milestone_id = plan["milestones"][0]["id"]
    updated = client.patch(
        f"/v1/strategic-plans/{plan['id']}/milestones/{milestone_id}",
        json={"state": "completed", "progress": 1},
    )
    assert updated.status_code == 200
    assert updated.json()["progress"] == 0.5
    assert updated.json()["recommended_focus"]


def test_blocker_marks_plan_at_risk() -> None:
    plan = client.post(
        "/v1/strategic-plans",
        json={
            "title": "Launch connector",
            "objective": "Ship a secure production connector.",
            "domain": "engineering",
            "milestones": [{"title": "Security review"}, {"title": "Release"}],
        },
    ).json()
    client.post(f"/v1/strategic-plans/{plan['id']}/activate", json={"approved_by": "Brano"})
    milestone_id = plan["milestones"][0]["id"]
    result = client.patch(
        f"/v1/strategic-plans/{plan['id']}/milestones/{milestone_id}",
        json={"blocker": "Security approval missing"},
    )
    assert result.status_code == 200
    assert result.json()["state"] == "at_risk"


def test_status_preserves_safety_flags() -> None:
    status = client.get("/v1/strategic-plans/status")
    assert status.status_code == 200
    assert status.json()["automatic_execution"] is False
    assert status.json()["automatic_order_execution"] is False
    assert status.json()["automatic_merge"] is False
