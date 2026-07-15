from fastapi.testclient import TestClient

from app.main import app
from app.orchestrator.service import orchestrator_service
from app.workers.service import worker_gateway_service

client = TestClient(app)


def setup_function() -> None:
    orchestrator_service.reset()
    worker_gateway_service.reset()


def test_mock_worker_dispatch_and_callback() -> None:
    task = client.post(
        "/v1/tasks",
        json={
            "title": "Build tests",
            "description": "Create worker gateway tests",
            "required_capabilities": ["python"],
        },
    ).json()
    worker = client.post(
        "/v1/workers",
        json={
            "name": "Codex Mock",
            "worker_type": "mock",
            "capabilities": ["python", "tests"],
        },
    ).json()

    response = client.post(
        "/v1/workers/dispatch",
        json={"task_id": task["id"], "worker_id": worker["id"]},
    )
    assert response.status_code == 200
    dispatch = response.json()
    assert dispatch["status"] == "running"
    assert dispatch["external_run_id"].startswith("mock-")

    callback = client.post(
        f"/v1/workers/dispatches/{dispatch['id']}/callback",
        json={"status": "completed", "output": "Tests added"},
    )
    assert callback.status_code == 200
    assert callback.json()["status"] == "completed"

    tasks = client.get("/v1/tasks").json()["items"]
    assert tasks[0]["status"] == "completed"


def test_non_mock_worker_requires_endpoint() -> None:
    response = client.post(
        "/v1/workers",
        json={"name": "Claude", "worker_type": "claude", "capabilities": []},
    )
    assert response.status_code == 400


def test_worker_capabilities_are_enforced() -> None:
    task = client.post(
        "/v1/tasks",
        json={
            "title": "Backend task",
            "description": "Needs Python",
            "required_capabilities": ["python"],
        },
    ).json()
    worker = client.post(
        "/v1/workers",
        json={"name": "UI Worker", "worker_type": "mock", "capabilities": ["ui"]},
    ).json()

    response = client.post(
        "/v1/workers/dispatch",
        json={"task_id": task["id"], "worker_id": worker["id"]},
    )
    assert response.status_code == 409
