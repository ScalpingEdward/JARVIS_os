from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.personal_ceo.service import personal_ceo_service


client = TestClient(app)


def setup_function() -> None:
    personal_ceo_service.reset()


def test_default_profile_addresses_master_brano() -> None:
    profile = client.get("/v1/personal-ceo/profile")
    assert profile.status_code == 200
    assert profile.json()["preferred_salutation"] == "MASTER Brano"
    assert profile.json()["assistant_name"] == "PHOENIX"


def test_builds_ranked_executive_briefing() -> None:
    deadline = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    payload = {
        "available_minutes": 180,
        "energy_level": 0.8,
        "items": [
            {
                "title": "Review XAUUSD setup before US news",
                "domain": "trading",
                "urgency": "critical",
                "state": "waiting_approval",
                "impact": 0.95,
                "confidence": 0.87,
                "deadline_at": deadline,
                "requires_approval": True,
                "source": "trade_analyst",
                "next_action": "Review the setup; do not execute automatically.",
            },
            {
                "title": "Merge backend documentation",
                "domain": "engineering",
                "urgency": "normal",
                "state": "ready",
                "impact": 0.4,
                "confidence": 0.9,
                "next_action": "Review CI and merge manually.",
            },
        ],
    }
    response = client.post("/v1/personal-ceo/briefings", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["salutation"] == "MASTER Brano"
    assert body["daily_focus"] == "Review XAUUSD setup before US news"
    assert body["top_priorities"][0]["domain"] == "trading"
    assert body["approvals"] == ["Review XAUUSD setup before US news"]
    assert body["automatic_execution"] is False
    assert body["automatic_order_execution"] is False


def test_profile_and_status_remain_human_controlled() -> None:
    profile = client.get("/v1/personal-ceo/profile").json()
    profile["preferred_salutation"] = "MASTER Brano"
    updated = client.put("/v1/personal-ceo/profile", json=profile)
    assert updated.status_code == 200
    status = client.get("/v1/personal-ceo/status").json()
    assert status["human_approval_required"] is True
    assert status["automatic_execution"] is False
    assert status["automatic_order_execution"] is False
