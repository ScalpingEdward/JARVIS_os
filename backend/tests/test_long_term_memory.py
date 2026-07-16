from fastapi.testclient import TestClient

from app.long_term_memory.service import long_term_memory_service
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    long_term_memory_service.reset()


def test_create_search_update_and_relationship() -> None:
    first = client.post(
        "/v1/long-term-memory",
        json={
            "memory_type": "semantic",
            "title": "Gold London setup",
            "content": "Liquidity sweep plus bullish displacement in London.",
            "tags": ["XAUUSD", "London", "liquidity"],
            "entities": ["XAUUSD"],
            "importance": 0.9,
            "confidence": 0.8,
        },
    )
    assert first.status_code == 201
    second = client.post(
        "/v1/long-term-memory",
        json={
            "memory_type": "experience",
            "title": "Wait for confirmation",
            "content": "Entries before displacement increased false signals.",
            "tags": ["XAUUSD", "confirmation"],
            "importance": 0.8,
        },
    )
    assert second.status_code == 201

    search = client.get("/v1/long-term-memory/search", params={"q": "Gold London"})
    assert search.status_code == 200
    assert search.json()[0]["title"] == "Gold London setup"

    memory_id = first.json()["id"]
    updated = client.patch(
        f"/v1/long-term-memory/{memory_id}",
        json={"confidence": 0.95, "reason": "Validated by additional evidence"},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    related = client.post(
        "/v1/long-term-memory/relationships",
        json={
            "source_memory_id": memory_id,
            "target_memory_id": second.json()["id"],
            "relationship": "learned_from",
            "strength": 0.9,
        },
    )
    assert related.status_code == 201


def test_trading_memory_is_advisory_and_has_statistics() -> None:
    response = client.post(
        "/v1/long-term-memory/trading",
        json={
            "instrument": "XAUUSD",
            "setup": "liquidity-sweep-fvg",
            "session": "London",
            "timeframe": "M15",
            "outcome": "win",
            "pnl_r": 3.0,
            "mfe_r": 3.5,
            "mae_r": -0.4,
            "conditions": ["H4 bullish", "news clear"],
            "mistakes": [],
            "lessons": "Waited for displacement close.",
        },
    )
    assert response.status_code == 201

    stats = client.get("/v1/long-term-memory/trading/statistics")
    assert stats.status_code == 200
    body = stats.json()
    assert body["advisory_only"] is True
    assert body["items"][0]["win_rate"] == 1.0

    status = client.get("/v1/long-term-memory/status").json()
    assert status["automatic_order_execution"] is False
    assert status["automatic_merge"] is False


def test_consolidation_archives_duplicates_and_keeps_audit() -> None:
    payload = {
        "memory_type": "project",
        "title": "Architecture decision",
        "content": "Use a local read-only MT5 bridge.",
        "tags": ["MT5", "bridge"],
        "importance": 0.8,
    }
    assert client.post("/v1/long-term-memory", json=payload).status_code == 201
    payload["content"] = "Keep broker credentials outside the backend."
    assert client.post("/v1/long-term-memory", json=payload).status_code == 201

    result = client.post(
        "/v1/long-term-memory/consolidate",
        json={"minimum_similarity": 0.8, "archive_duplicates": True, "actor": "test"},
    )
    assert result.status_code == 200
    assert result.json()["clusters"] == 1
    assert result.json()["archived"] == 1
    assert result.json()["generated_experiences"] == 1

    audit = client.get("/v1/long-term-memory/audit")
    assert audit.status_code == 200
    assert any(item["action"] == "consolidated" for item in audit.json())
