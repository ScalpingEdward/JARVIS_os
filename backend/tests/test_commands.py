from fastapi.testclient import TestClient

from app.main import app
from app.memory.service import memory_service
from app.orchestrator.service import orchestrator_service

client = TestClient(app)


def setup_function() -> None:
    memory_service.reset()
    orchestrator_service.reset()


def test_create_memory_through_command() -> None:
    response = client.post(
        "/v1/commands/execute",
        json={
            "action": "memory.create",
            "arguments": {
                "content": "Remember the JARVIS roadmap",
                "category": "project",
                "tags": ["jarvis"],
                "priority": 4,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["data"]["content"] == "Remember the JARVIS roadmap"
    assert len(memory_service.list_all()) == 1


def test_create_and_assign_task_through_commands() -> None:
    agent = client.post(
        "/v1/agents",
        json={"name": "Codex", "role": "developer", "capabilities": ["python"]},
    )
    assert agent.status_code == 201

    created = client.post(
        "/v1/commands/execute",
        json={
            "action": "task.create",
            "arguments": {
                "title": "Build command endpoint",
                "description": "Implement and test the command layer",
                "priority": 80,
                "required_capabilities": ["python"],
            },
        },
    )
    assert created.status_code == 200
    assert created.json()["data"]["status"] == "queued"

    assigned = client.post(
        "/v1/commands/execute",
        json={"action": "task.assign_next", "arguments": {}},
    )
    assert assigned.status_code == 200
    assert assigned.json()["data"]["status"] == "assigned"


def test_project_status_command() -> None:
    response = client.post(
        "/v1/commands/execute",
        json={"action": "project.status", "arguments": {}},
    )
    assert response.status_code == 200
    assert response.json()["data"] == {
        "queued_tasks": 0,
        "active_tasks": 0,
        "completed_tasks": 0,
        "registered_agents": 0,
        "available_agents": 0,
    }


def test_invalid_command_arguments_return_400() -> None:
    response = client.post(
        "/v1/commands/execute",
        json={"action": "task.create", "arguments": {"title": "Missing description"}},
    )
    assert response.status_code == 400
