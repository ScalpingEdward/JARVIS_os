from fastapi.testclient import TestClient

from app.autonomous_research.service import autonomous_research_service
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    autonomous_research_service.reset()


def event_payload(title: str, claim: str, primary: bool = True) -> dict:
    return {
        "title": title,
        "summary": "NVIDIA AI chip development affects semiconductor markets.",
        "source": {
            "name": "Company filing",
            "source_type": "company",
            "credibility": 0.9,
            "primary_source": primary,
        },
        "entities": ["NVIDIA", "TSMC", "NASDAQ"],
        "topics": ["AI", "semiconductors"],
        "claims": [claim],
        "evidence": ["official filing", "company statement", "product release"],
        "relevance": 0.9,
        "impacts": [
            {
                "domain": "market",
                "target": "NASDAQ",
                "direction": 0.6,
                "magnitude": 0.7,
                "horizon": "medium-term",
                "rationale": "AI semiconductor demand may support the index.",
            }
        ],
    }


def test_verifies_high_quality_primary_source_and_builds_brief() -> None:
    created = client.post("/v1/research-network/events", json=event_payload("NVIDIA launches new AI chip", "chip launch will increase capacity"))
    assert created.status_code == 201
    assert created.json()["state"] == "verified"
    assert created.json()["confidence"] >= 0.65
    brief = client.get("/v1/research-network/brief").json()
    assert "NVIDIA" in brief["key_entities"]
    assert brief["opportunities"]


def test_detects_duplicate_and_contradiction() -> None:
    first = client.post("/v1/research-network/events", json=event_payload("Capacity outlook", "capacity will increase")).json()
    duplicate = client.post("/v1/research-network/events", json=event_payload("Capacity outlook", "capacity will increase")).json()
    assert duplicate["state"] == "duplicate"
    assert duplicate["duplicate_of"] == first["id"]

    disputed_payload = event_payload("Capacity warning", "capacity will decrease")
    disputed_payload["summary"] = "A separate source expects production constraints and lower capacity."
    disputed = client.post("/v1/research-network/events", json=disputed_payload).json()
    assert disputed["state"] == "disputed"
    assert first["id"] in disputed["contradiction_ids"]


def test_safety_flags_remain_disabled() -> None:
    payload = client.get("/v1/research-network/status").json()
    assert payload["automatic_order_execution"] is False
    assert payload["automatic_merge"] is False
