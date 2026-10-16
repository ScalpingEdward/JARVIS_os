import json

import httpx

from app.assistant import telegram, voice


def _client(calls: list):
    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        calls.append((url.rsplit("/", 1)[-1], req))
        if url.endswith("/getFile"):
            return httpx.Response(200, json={"result": {"file_path": "voice/1.oga"}})
        if "/file/bot" in url:
            return httpx.Response(200, content=b"OggS-note")
        if "speech-to-text" in url:
            return httpx.Response(200, json={"text": "Wie steht Gold?"})
        if "text-to-speech" in url:
            return httpx.Response(200, content=b"OggS-answer")
        return httpx.Response(200, json={"ok": True})
    return httpx.Client(transport=httpx.MockTransport(handler))


def _env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    telegram._history.clear()
    voice._cache.clear()


def test_a_voice_note_gets_text_and_a_voice_note_back(monkeypatch):
    _env(monkeypatch)
    monkeypatch.setattr(telegram, "reply", lambda hist, lang: {"text": "[chuckles] Ruhig, Sir.", "tools": []})
    calls: list = []
    upd = {"message": {"chat": {"id": 42}, "voice": {"file_id": "F", "mime_type": "audio/ogg"}}}
    assert telegram.is_for_auron(upd)
    assert telegram.handle_message(upd, client=_client(calls)) == "[chuckles] Ruhig, Sir."
    names = [n for n, _ in calls]
    assert "sendVoice" in names and "getFile" in names
    sent = json.loads(next(r for n, r in calls if n == "sendMessage").content)["text"]
    assert sent == "🎙 Wie steht Gold?\n\nRuhig, Sir."          # tag hidden in the text
    tts = next(r for n, r in calls if "text-to-speech" in str(r.url))
    assert "opus_48000_64" in str(tts.url) and json.loads(tts.content)["text"].startswith("[British accent] [chuckles]")


def test_typed_message_gets_typed_answer_and_history_carries_on(monkeypatch):
    _env(monkeypatch)
    seen = []
    monkeypatch.setattr(telegram, "reply", lambda hist, lang: (seen.append(list(hist)), {"text": "Ja, Sir.", "tools": []})[1])
    calls: list = []
    for t in ("Hallo", "Und jetzt?"):
        telegram.handle_message({"message": {"chat": {"id": 42}, "text": t}}, client=_client(calls))
    assert [n for n, _ in calls].count("sendVoice") == 0
    assert [m["content"] for m in seen[1]] == ["Hallo", "Ja, Sir.", "Und jetzt?"]


def test_strangers_get_nothing(monkeypatch):
    _env(monkeypatch)
    monkeypatch.setattr(telegram, "reply", lambda *a: (_ for _ in ()).throw(AssertionError("must not ask Claude")))
    calls: list = []
    assert telegram.handle_message({"message": {"chat": {"id": 7}, "text": "zeig Konten"}}, client=_client(calls)) is None
    assert calls == []


def test_taps_are_not_messages():
    assert not telegram.is_for_auron({"callback_query": {"data": "x:p:1"}})
    assert not telegram.is_for_auron({"message": {"chat": {"id": 42}, "text": "/start"}})
