from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_control_center_is_served() -> None:
    response = client.get("/v1/execution/control-center")
    assert response.status_code == 200
    assert "JARVIS Control Center" in response.text
    assert "MASTER COMMAND" in response.text


def test_mobile_voice_console_is_served() -> None:
    response = client.get("/v1/execution/mobile-voice")
    assert response.status_code == 200
    assert "JARVIS Mobile Voice" in response.text
    assert "Sprich mit JARVIS" in response.text
    assert "kritische Aktion" in response.text.lower()


def test_control_center_assets_are_served_and_unknown_assets_are_blocked() -> None:
    css = client.get("/v1/execution/control-center/assets/styles.css")
    js = client.get("/v1/execution/control-center/assets/app.js")
    voice_js = client.get("/v1/execution/control-center/assets/voice.js")
    missing = client.get("/v1/execution/control-center/assets/secret.txt")

    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]
    assert js.status_code == 200
    assert "javascript" in js.headers["content-type"]
    assert voice_js.status_code == 200
    assert "javascript" in voice_js.headers["content-type"]
    assert missing.status_code == 404
