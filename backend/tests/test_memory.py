from fastapi.testclient import TestClient

from app.main import app
from app.memory.service import memory_service

client = TestClient(app)


def setup_function() -> None:
    memory_service.store.clear()


def test_create_list_search_and_delete_memory() -> None:
    created = client.post(
        "/v1/memory",
        json={
            "content": "Trade FTMO only in the morning",
            "category": "trading",
            "priority": 3,
            "tags": ["ftmo", "routine"],
        },
    )
    assert created.status_code == 201
    memory = created.json()
    assert memory["category"] == "trading"
    assert memory["priority"] == 3

    listed = client.get("/v1/memory", params={"category": "trading"})
    assert listed.status_code == 200
    assert listed.json()["count"] == 1

    searched = client.get("/v1/memory/search", params={"q": "FTMO"})
    assert searched.status_code == 200
    assert searched.json()["count"] == 1

    deleted = client.delete(f"/v1/memory/{memory['id']}")
    assert deleted.status_code == 204

    missing = client.delete(f"/v1/memory/{memory['id']}")
    assert missing.status_code == 404


def test_memory_validation_rejects_empty_content() -> None:
    response = client.post(
        "/v1/memory",
        json={"content": "", "category": "general"},
    )
    assert response.status_code == 422


def test_search_prioritizes_high_priority_results() -> None:
    client.post(
        "/v1/memory",
        json={"content": "Jarvis memory note", "priority": 1},
    )
    client.post(
        "/v1/memory",
        json={"content": "Critical Jarvis memory note", "priority": 4},
    )

    response = client.get("/v1/memory/search", params={"q": "Jarvis"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["priority"] == 4
