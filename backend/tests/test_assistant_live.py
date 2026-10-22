import json

import httpx

from app.assistant import live


def test_every_tool_goes_to_the_agent_with_simple_described_parameters():
    tools = live.client_tools()
    names = {t["name"] for t in tools}
    assert {"trading_status", "spotify", "dashboard_design", "own_code"} <= names
    for t in tools:
        assert t["type"] == "client" and t["expects_response"]
        for p in t["parameters"]["properties"].values():
            assert p["type"] in ("string", "integer", "number", "boolean") and p["description"]
    cfg = live.agent_config()["conversation_config"]
    assert cfg["tts"]["voice_id"] == live.VOICE and "LIVE-GESPRÄCH" in cfg["agent"]["prompt"]["prompt"]


def test_object_parameters_come_back_as_objects():
    out = live.run_tool("dashboard_design", {"action": "get"})
    assert "catalog" in out or "look" in out
    assert live.run_tool("nope", {}) == "unknown tool nope"


def test_the_agent_is_made_once_updated_when_it_changes_and_errors_say_what(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    live._store({})
    calls = []

    def handler(req):
        calls.append((req.method, req.url.path))
        if req.url.path.endswith("/agents/create"):
            return httpx.Response(200, json={"agent_id": "ag1"})
        if "get-signed-url" in req.url.path:
            return httpx.Response(200, json={"signed_url": "wss://x"})
        return httpx.Response(200, json={})

    c = httpx.Client(transport=httpx.MockTransport(handler))
    assert live.session(c) == {"signed_url": "wss://x", "agent_id": "ag1"}
    live.session(c)
    assert [m for m, p in calls if p.endswith("/agents/create")] == ["POST"]          # made once
    assert not any(m == "PATCH" for m, _ in calls)                                    # nothing changed
    live._store({"agent_id": "ag1", "hash": "old"})
    live.session(c)
    assert ("PATCH", "/v1/convai/agents/ag1") in calls                                # changed: updated
    deny = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(
        401, json={"detail": {"message": "missing the permission convai_read"}})))
    live._store({})
    try:
        live.session(deny)
        assert False
    except live.LiveError as exc:
        assert "convai_read" in str(exc)
