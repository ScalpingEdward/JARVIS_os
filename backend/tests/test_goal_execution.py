from fastapi.testclient import TestClient

from app.company_runtime.models import RuntimeStatus, RuntimeUpdate
from app.company_runtime.service import company_runtime_service
from app.goal_execution.service import goal_execution_service
from app.main import app
from app.strategic_planner.service import strategic_planner_service

client = TestClient(app)


def setup_function() -> None:
    strategic_planner_service.reset()
    company_runtime_service.reset()
    goal_execution_service.reset()


def create_active_plan() -> dict:
    plan = client.post(
        "/v1/strategic-plans",
        json={
            "title": "PHOENIX roadmap",
            "objective": "Deliver controlled milestones",
            "domain": "engineering",
            "milestones": [
                {"title": "Backend", "description": "Build backend", "priority": 1},
                {"title": "QA", "description": "Validate release", "priority": 2, "dependencies": ["Backend"]},
            ],
        },
    ).json()
    client.post(f"/v1/strategic-plans/{plan['id']}/activate", json={"approved_by": "Brano"})
    return plan


def test_bridge_requires_human_approval() -> None:
    plan = create_active_plan()
    bridge = client.post("/v1/goal-execution", json={"plan_id": plan["id"]}).json()
    assert bridge["state"] == "awaiting_approval"
    assert len(company_runtime_service.list_all()) == 0
    approved = client.post(f"/v1/goal-execution/{bridge['id']}/approve", json={"approved_by": "Brano"}).json()
    assert approved["state"] == "active"
    assert len(approved["links"]) == 2


def test_sync_updates_plan_progress() -> None:
    plan = create_active_plan()
    bridge = client.post("/v1/goal-execution", json={"plan_id": plan["id"], "approved_by": "Brano"}).json()
    mission_id = bridge["links"][0]["mission_id"]
    company_runtime_service.update(mission_id, RuntimeUpdate(status=RuntimeStatus.completed))
    company_runtime_service.approve(mission_id)
    synced = client.post(f"/v1/goal-execution/{bridge['id']}/sync").json()
    assert synced["links"][0]["progress"] == 1


def test_safety_flags_remain_disabled() -> None:
    payload = client.get("/v1/goal-execution/status").json()
    assert payload["automatic_execution"] is False
    assert payload["automatic_order_execution"] is False
    assert payload["automatic_merge"] is False
