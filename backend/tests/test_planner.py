from fastapi.testclient import TestClient

from app.main import app
from app.orchestrator.service import orchestrator_service
from app.planner.service import planner_service

client = TestClient(app)


def setup_function() -> None:
    orchestrator_service.reset()
    planner_service.reset()


def test_planner_creates_ordered_dependency_plan() -> None:
    response = client.post(
        "/v1/planner/plan",
        json={"goal": "Build a Telegram signal parser", "create_tasks": False},
    )
    assert response.status_code == 200
    payload = response.json()
    steps = payload["plan"]["steps"]
    assert payload["tasks_created"] is False
    assert len(steps) >= 7
    assert [step["sequence"] for step in steps] == list(range(1, len(steps) + 1))
    assert steps[1]["depends_on"] == [steps[0]["id"]]
    assert steps[-1]["approval_required"] is True


def test_planner_can_create_orchestrator_tasks() -> None:
    response = client.post(
        "/v1/planner/plan",
        json={
            "goal": "Build a safe dashboard",
            "create_tasks": True,
            "preferred_workers": ["codex", "claude"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    step_count = len(payload["plan"]["steps"])
    assert payload["tasks_created"] is True
    assert len(payload["plan"]["created_task_ids"]) == step_count
    assert len(orchestrator_service.list_tasks()) == step_count


def test_planner_rejects_short_goal() -> None:
    response = client.post("/v1/planner/plan", json={"goal": "x"})
    assert response.status_code == 422
