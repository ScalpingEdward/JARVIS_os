from fastapi.testclient import TestClient

from app.main import app
from app.voice.service import voice_control_service

client = TestClient(app)


def setup_function() -> None:
    voice_control_service.reset()


def test_wake_word_answers_master_brano_and_activates_context() -> None:
    wake = client.post("/v1/voice/browser", json={"transcript": "PHOENIX", "session_id": "desk"})
    assert wake.status_code == 200
    assert wake.json()["text"] == "Yes, MASTER Brano?"
    assert wake.json()["intent"] == "wake"
    assert wake.json()["session_active"] is True

    follow_up = client.post("/v1/voice/browser", json={"transcript": "zeige mir XAUUSD", "session_id": "desk"})
    assert follow_up.status_code == 200
    assert follow_up.json()["intent"] == "market"
    assert follow_up.json()["ui_action"] == "focus_market"
    assert follow_up.json()["ui_target"] == "XAUUSD"


def test_command_without_wake_word_is_rejected_for_inactive_session() -> None:
    response = client.post("/v1/voice/browser", json={"transcript": "status", "session_id": "new-session"})
    assert response.status_code == 403
    assert "Wake-Name" in response.json()["detail"]


def test_briefing_and_approvals_are_ui_only_actions() -> None:
    briefing = client.post("/v1/voice/browser", json={"transcript": "PHOENIX was ist heute wichtig", "session_id": "desk"})
    assert briefing.status_code == 200
    assert briefing.json()["ui_action"] == "open_briefing"

    approvals = client.post("/v1/voice/browser", json={"transcript": "freigaben", "session_id": "desk"})
    assert approvals.status_code == 200
    assert approvals.json()["ui_action"] == "open_approvals"
    assert "nichts automatisch" in approvals.json()["text"].lower()


def test_voice_status_and_history_preserve_safety_flags() -> None:
    client.post("/v1/voice/browser", json={"transcript": "PHOENIX", "session_id": "desk"})
    history = client.get("/v1/voice/history", params={"session_id": "desk"}).json()
    assert history["count"] == 1
    assert history["items"][0]["intent"] == "wake"

    status = client.get("/v1/voice/status").json()
    assert status["settings"]["owner_salutation"] == "MASTER Brano"
    assert status["browser_speech_supported"] is True
    assert status["automatic_execution"] is False
    assert status["automatic_order_execution"] is False
    assert status["automatic_merge"] is False
