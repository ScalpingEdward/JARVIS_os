from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_model_providers() -> None:
    response = client.get("/v1/models/providers")

    assert response.status_code == 200
    assert response.json() == {"providers": ["mock"]}


def test_generate_model_response() -> None:
    response = client.post(
        "/v1/models/generate",
        json={"prompt": "Plan phase 2", "task_type": "planning"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "provider": "mock",
        "model": "jarvis-mock-v1",
        "content": "Mock response for planning: Plan phase 2",
    }


def test_generate_rejects_unknown_provider() -> None:
    response = client.post(
        "/v1/models/generate",
        json={"prompt": "Hello", "provider": "unknown"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown model provider: unknown"


def test_generate_rejects_empty_prompt() -> None:
    response = client.post("/v1/models/generate", json={"prompt": ""})

    assert response.status_code == 422
