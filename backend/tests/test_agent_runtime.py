from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.runtime.models import RunStatus, RuntimeStatus
from app.runtime.service import agent_runtime_service

client = TestClient(app)


def setup_function() -> None:
    agent_runtime_service.reset()


def test_register_worker_create_run_and_dispatch() -> None:
    worker = client.post(
        "/v1/runtime/workers",
        json={
            "name": "Codex Runtime",
            "provider": "mock",
            "capabilities": ["python", "tests"],
            "max_parallel_runs": 2,
        },
    )
    assert worker.status_code == 201

    run = client.post(
        "/v1/runtime/runs",
        json={
            "title": "Build runtime tests",
            "payload": {"repository": "JARVIS_os"},
            "required_capabilities": ["python"],
        },
    )
    assert run.status_code == 201

    dispatched = client.post("/v1/runtime/runs/dispatch-next")
    assert dispatched.status_code == 200
    assert dispatched.json()["status"] == "running"
    assert dispatched.json()["worker_id"] == worker.json()["id"]


def test_completion_releases_worker() -> None:
    worker = agent_runtime_service.register_worker(
        __import__("app.runtime.models", fromlist=["RuntimeWorkerCreate"]).RuntimeWorkerCreate(
            name="Mock", provider="mock", capabilities=["python"]
        )
    )
    run = agent_runtime_service.create_run(
        __import__("app.runtime.models", fromlist=["RuntimeRunCreate"]).RuntimeRunCreate(
            title="Task", required_capabilities=["python"]
        )
    )
    agent_runtime_service.dispatch_next()
    result = client.patch(
        f"/v1/runtime/runs/{run.id}",
        json={"status": "completed", "output": "done"},
    )
    assert result.status_code == 200
    assert result.json()["status"] == "completed"
    assert agent_runtime_service.list_workers()[0].status == RuntimeStatus.idle
    assert agent_runtime_service.list_workers()[0].active_runs == 0


def test_retry_and_summary() -> None:
    client.post(
        "/v1/runtime/workers",
        json={"name": "Mock", "provider": "mock", "capabilities": ["python"], "max_retries": 2},
    )
    run = client.post(
        "/v1/runtime/runs",
        json={"title": "Retry me", "required_capabilities": ["python"]},
    ).json()
    client.post("/v1/runtime/runs/dispatch-next")
    client.patch(f"/v1/runtime/runs/{run['id']}", json={"status": "failed", "error": "boom"})
    retry = client.post(f"/v1/runtime/runs/{run['id']}/retry")
    assert retry.status_code == 200
    assert retry.json()["status"] == "retrying"
    summary = client.get("/v1/runtime/summary").json()
    assert summary["queued_runs"] == 1


def test_stale_worker_becomes_offline() -> None:
    worker = agent_runtime_service.register_worker(
        __import__("app.runtime.models", fromlist=["RuntimeWorkerCreate"]).RuntimeWorkerCreate(
            name="Stale", provider="mock"
        )
    )
    worker.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    response = client.post("/v1/runtime/discover?stale_after_seconds=60")
    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "offline"


def test_non_mock_worker_requires_endpoint() -> None:
    response = client.post(
        "/v1/runtime/workers",
        json={"name": "Claude", "provider": "claude", "capabilities": ["reasoning"]},
    )
    assert response.status_code == 400
