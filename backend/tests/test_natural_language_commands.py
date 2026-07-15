from fastapi.testclient import TestClient

from app.main import app
from app.memory.service import memory_service
from app.orchestrator.service import orchestrator_service

client = TestClient(app)


def setup_function() -> None:
    memory_service.reset()
    orchestrator_service.reset()


def test_german_memory_command_is_parsed_and_executed() -> None:
    response = client.post(
        "/v1/commands/natural",
        json={"text": "Merke dir, dass ich nur morgens trade."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["command"]["action"] == "memory.create"
    assert payload["result"]["status"] == "completed"
    assert payload["result"]["data"]["content"] == "ich nur morgens trade"
    assert len(memory_service.list_all()) == 1


def test_english_task_command_can_be_previewed_without_execution() -> None:
    response = client.post(
        "/v1/commands/natural",
        json={"text": "Create a task: Build voice input", "execute": False},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["command"]["action"] == "task.create"
    assert payload["command"]["arguments"]["title"] == "Build voice input"
    assert payload["result"] is None
    assert orchestrator_service.list_tasks() == []


def test_project_status_phrase_is_supported() -> None:
    response = client.post(
        "/v1/commands/natural",
        json={"text": "Zeige mir den Projektstatus"},
    )
    assert response.status_code == 200
    assert response.json()["result"]["data"]["queued_tasks"] == 0


def test_assign_next_phrase_uses_existing_safe_command() -> None:
    client.post(
        "/v1/agents",
        json={"name": "Worker", "role": "developer", "capabilities": []},
    )
    client.post(
        "/v1/tasks",
        json={"title": "Task", "description": "Do the task"},
    )
    response = client.post(
        "/v1/commands/natural",
        json={"text": "Weise den nächsten Worker zu"},
    )
    assert response.status_code == 200
    assert response.json()["result"]["data"]["status"] == "assigned"


def test_unknown_natural_language_command_is_rejected() -> None:
    response = client.post(
        "/v1/commands/natural",
        json={"text": "Öffne meinen Browser und kaufe etwas"},
    )
    assert response.status_code == 422
