from fastapi.testclient import TestClient

from app.main import app
from app.orchestrator.service import orchestrator_service

client = TestClient(app)


def setup_function() -> None:
    orchestrator_service.reset()


def test_register_agent_create_task_and_assign() -> None:
    agent_response = client.post(
        "/v1/agents",
        json={
            "name": "Codex Worker",
            "role": "developer",
            "capabilities": ["python", "tests"],
        },
    )
    assert agent_response.status_code == 201

    task_response = client.post(
        "/v1/tasks",
        json={
            "title": "Build endpoint",
            "description": "Implement and test one API endpoint.",
            "priority": 90,
            "required_capabilities": ["python"],
        },
    )
    assert task_response.status_code == 201
    assert task_response.json()["status"] == "queued"

    assignment = client.post("/v1/orchestrator/assign-next")
    assert assignment.status_code == 200
    payload = assignment.json()
    assert payload["status"] == "assigned"
    assert payload["assigned_agent_id"] == agent_response.json()["id"]

    status_response = client.get("/v1/orchestrator/status")
    assert status_response.status_code == 200
    assert status_response.json() == {
        "queued_tasks": 0,
        "active_tasks": 1,
        "completed_tasks": 0,
        "registered_agents": 1,
        "available_agents": 0,
    }


def test_higher_priority_task_is_assigned_first() -> None:
    client.post(
        "/v1/agents",
        json={"name": "Worker", "role": "developer", "capabilities": []},
    )
    low = client.post(
        "/v1/tasks",
        json={"title": "Low", "description": "Low priority", "priority": 10},
    ).json()
    high = client.post(
        "/v1/tasks",
        json={"title": "High", "description": "High priority", "priority": 100},
    ).json()

    assigned = client.post("/v1/orchestrator/assign-next").json()
    assert assigned["id"] == high["id"]
    assert assigned["id"] != low["id"]


def test_incompatible_agent_returns_conflict() -> None:
    client.post(
        "/v1/agents",
        json={"name": "UI Worker", "role": "frontend", "capabilities": ["ui"]},
    )
    client.post(
        "/v1/tasks",
        json={
            "title": "Backend",
            "description": "Python task",
            "required_capabilities": ["python"],
        },
    )

    response = client.post("/v1/orchestrator/assign-next")
    assert response.status_code == 409


def test_completing_task_releases_agent() -> None:
    agent = client.post(
        "/v1/agents",
        json={"name": "Worker", "role": "developer", "capabilities": []},
    ).json()
    client.post(
        "/v1/tasks",
        json={"title": "Task", "description": "Complete me"},
    )
    task = client.post("/v1/orchestrator/assign-next").json()

    response = client.patch(
        f"/v1/tasks/{task['id']}/status",
        json={"status": "completed"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    agents = client.get("/v1/agents").json()["items"]
    assert agents[0]["id"] == agent["id"]
    assert agents[0]["status"] == "available"
