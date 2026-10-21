import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.assistant import brain, tools
from app.main import app
from app.watchlist.service import watchlist_service

client = TestClient(app)


def _fake(responses: list[dict], seen: list[dict]) -> httpx.Client:
    """An Anthropic stand-in answering with the given bodies in order."""
    it = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=next(it))
    return httpx.Client(transport=httpx.MockTransport(handler))


def setup_function() -> None:
    watchlist_service.reset()


def test_runs_a_tool_and_answers_with_its_result(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    seen: list[dict] = []
    c = _fake([
        {"stop_reason": "tool_use", "content": [{"type": "tool_use", "id": "t1", "name": "watchlist", "input": {}}]},
        {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Die Watchlist ist leer."}]},
    ], seen)
    out = brain.reply([{"role": "user", "content": "Wie steht Gold?"}], client=c)
    assert out == {"text": "Die Watchlist ist leer.", "tools": ["watchlist"]}
    result = seen[1]["messages"][-1]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "t1" and result["is_error"] is False
    assert json.loads(result["content"])["items"] == []
    assert any(t["name"] == "web_search" for t in seen[0]["tools"])


def test_a_failing_tool_reaches_the_model_as_an_error_not_a_crash(monkeypatch):
    monkeypatch.setitem(tools._RUN, "trading_status", lambda **_: 1 / 0)
    text, failed = tools.run("trading_status", {})
    assert failed and "ZeroDivisionError" in text
    assert tools.run("close_everything", {})[1] is True


def test_language_is_part_of_the_prompt():
    assert "English" in brain.system_prompt("en") and "Deutsch" in brain.system_prompt("de")


def test_gives_up_after_too_many_tool_rounds(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    loop = {"stop_reason": "tool_use", "content": [{"type": "tool_use", "id": "t", "name": "watchlist", "input": {}}]}
    with pytest.raises(brain.AssistantError, match="tool rounds"):
        brain.reply([{"role": "user", "content": "x"}], client=_fake([loop] * brain.MAX_ROUNDS, []))


def test_endpoint_refuses_when_the_last_turn_is_not_brano(monkeypatch):
    r = client.post("/v1/assistant/chat", json={"messages": [{"role": "assistant", "content": "hi"}]})
    assert r.status_code == 422


def test_endpoint_reports_a_missing_key_as_502(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = client.post("/v1/assistant/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 502 and "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_speak_keeps_tags_only_for_models_that_play_them(monkeypatch):
    from app.assistant import voice
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    voice._cache.clear()
    sent: list[dict] = []
    c = httpx.Client(transport=httpx.MockTransport(
        lambda req: (sent.append(json.loads(req.content)), httpx.Response(200, content=b"ID3mp3"))[1]))
    assert voice.speak("[laughs] Hallo", "elevenlabs", "v1", "eleven_v4", "British accent", client=c) == b"ID3mp3"
    voice.speak("[laughs] Hallo", "elevenlabs", "v1", "eleven_multilingual_v2", "British accent", client=c)
    voice.speak("[laughs] Hallo", "elevenlabs", "v1", "eleven_v4", "British accent", client=c)   # cached, no second call
    assert [s["text"] for s in sent] == ["[British accent] [laughs] Hallo", "Hallo"]


def test_speak_endpoint_without_key_is_502(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    from app.assistant import voice
    voice._cache.clear()
    r = client.post("/v1/assistant/speak", json={"text": "Hallo"})
    assert r.status_code == 502 and "ELEVENLABS_API_KEY" in r.json()["detail"]
    assert client.get("/v1/assistant/voices").json()["elevenlabs"]["available"] is False


def test_listen_sends_the_recording_and_returns_the_text(monkeypatch):
    from app.assistant import voice
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    seen = []
    c = httpx.Client(transport=httpx.MockTransport(
        lambda req: (seen.append(req), httpx.Response(200, json={"text": " Wie steht Gold? "}))[1]))
    assert voice.transcribe(b"webm-bytes", "audio/webm;codecs=opus", "de", client=c) == "Wie steht Gold?"
    body = seen[0].content
    assert b"scribe_v2" in body and b"webm-bytes" in body and b'filename="speech.webm"' in body


def test_listen_refuses_empty_audio(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    r = client.post("/v1/assistant/listen", content=b"", headers={"content-type": "audio/webm"})
    assert r.status_code == 502 and "no audio" in r.json()["detail"]


def test_only_the_first_screen_may_speak_an_announcement():
    from app.assistant import api
    api._claimed.clear()
    assert api.announce_claim(api.ClaimIn(key="Sir, NINJA hat einen Trade geschlossen.")) == {"speak": True}
    assert api.announce_claim(api.ClaimIn(key="Sir, NINJA hat einen Trade geschlossen.")) == {"speak": False}
    assert api.announce_claim(api.ClaimIn(key="Sir, eine wichtige E-Mail")) == {"speak": True}


def test_a_picture_goes_to_claude_as_an_image_block_and_bad_ones_are_refused():
    import pytest
    from pydantic import ValidationError
    from app.assistant import api
    tiny = "data:image/png;base64,iVBORw0KGgo="
    msgs = api.ChatIn(messages=[{"role": "user", "content": "Was siehst du?", "image": tiny}]).messages
    out = api._turns(msgs)
    assert out[0]["content"][0] == {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "iVBORw0KGgo="}}
    assert out[0]["content"][1] == {"type": "text", "text": "Was siehst du?"}
    assert api._turns(api.ChatIn(messages=[{"role": "user", "content": "hi"}]).messages) == [{"role": "user", "content": "hi"}]
    with pytest.raises(ValidationError):
        api.ChatIn(messages=[{"role": "user", "content": "x", "image": "data:text/html;base64,PHNjcmlwdD4="}])
