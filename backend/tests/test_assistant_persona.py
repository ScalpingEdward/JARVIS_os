import pytest

from app.assistant import persona, tools
from app.assistant.brain import system_prompt


@pytest.fixture(autouse=True)
def clean():
    persona._put(persona.MEMORY_KEY, [])
    persona._put(persona.HUMOR_KEY, persona.DEFAULT_HUMOR)
    yield
    persona._put(persona.MEMORY_KEY, [])
    persona._put(persona.HUMOR_KEY, persona.DEFAULT_HUMOR)


def test_what_brano_teaches_goes_into_every_prompt_until_he_deletes_it():
    out, failed = tools.run("memory", {"action": "remember", "text": "Ich trinke meinen Kaffee schwarz."})
    assert not failed and "remembered" in out
    tools.run("memory", {"action": "remember", "text": "ich trinke meinen   kaffee schwarz."})   # the same once
    assert len(persona.memories()) == 1
    assert "- Ich trinke meinen Kaffee schwarz." in system_prompt("de")
    tools.run("memory", {"action": "forget", "memory_id": persona.memories()[0]["id"]})
    assert "Kaffee" not in system_prompt("de")


def test_humor_level_and_style_are_set_by_word_and_land_in_the_prompt():
    assert "Stärke 5/10" in system_prompt("de")
    out, failed = tools.run("humor", {"action": "set", "level": 9, "style": "Sarkastisch"})
    assert not failed and '"level": 9' in out
    p = system_prompt("de")
    assert "Stärke 9/10" in p and "sarkastisch" in p and "fast immer" in p
    tools.run("humor", {"action": "set", "level": 0})
    assert "Gar kein Humor" in system_prompt("de")


def test_nonsense_is_refused():
    with pytest.raises(persona.PersonaError):
        persona.set_humor(level=11)
    with pytest.raises(persona.PersonaError):
        persona.set_humor(style="schwarz")
    with pytest.raises(persona.PersonaError):
        persona.remember("x" * 301)
    with pytest.raises(persona.PersonaError):
        persona.forget(999)


def test_auron_learns_from_branos_words_and_forgets_what_is_over(monkeypatch):
    from app.assistant import learn
    monkeypatch.setattr(learn, "decide", lambda u, a, client=None: {"add": [
        {"text": "Brano arbeitet im Schichtdienst.", "kind": "fact"},
        {"text": "Brano ist bis 18 Uhr auf Arbeit.", "kind": "now", "days": 0.5},
        {"text": "Sein Passwort ist hunter2.", "kind": "fact"}], "drop": []})
    stored = learn.learn("Ich bin jetzt auf Arbeit bis 18 Uhr, Schichtdienst halt.", "Viel Erfolg, Sir.")
    assert [m["text"] for m in stored] == ["Brano arbeitet im Schichtdienst.", "Brano ist bis 18 Uhr auf Arbeit."]
    assert all(m["by"] == "auron" for m in stored)
    p = system_prompt("de")
    assert "Schichtdienst" in p and "Gerade aktuell" in p and "hunter2" not in p
    work = next(m for m in persona.memories() if m["kind"] == "now")
    fact = next(m for m in persona.memories() if m["kind"] == "fact")
    monkeypatch.setattr(learn, "decide", lambda u, a, client=None: {"add": [], "drop": [work["id"], fact["id"]]})
    learn.learn("So, ich bin wieder zu Hause, endlich.", "Wie war die Arbeit, Sir?")
    assert [m["text"] for m in persona.memories()] == ["Brano arbeitet im Schichtdienst."]   # facts are never dropped


def test_secrets_and_short_words_teach_nothing(monkeypatch):
    from app.assistant import learn
    monkeypatch.setattr(learn, "decide", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not ask")))
    assert learn.learn("ok", "") == []
    assert learn.learn("Meine IBAN ist DE12 3456 7890 1234 5678 90", "") == []


def test_a_now_entry_runs_out_by_itself(monkeypatch):
    m = persona.remember("Brano ist beim Zahnarzt.", by="auron", kind="now", days=1)
    assert m in persona.memories()
    monkeypatch.setattr(persona.time, "time", lambda: m["until"] + 1)
    assert persona.memories() == []


def test_language_and_address_by_word_reach_prompt_ear_and_live_talk():
    from app.assistant import live, voice
    try:
        out, failed = tools.run("language", {"action": "set_language", "language": "Tschechisch"})
        assert not failed and '"cs"' in out
        assert "Sprache der Antwort: Čeština" in system_prompt("de")      # the browser's lang no longer decides
        assert voice._lang() == "cs" and live.agent_config()["conversation_config"]["agent"]["language"] == "cs"
        assert live._first_words() == "Ano, pane?"
        tools.run("language", {"action": "set_address", "address": "name"})
        assert "Brano an und duze" in system_prompt("de") and live._first_words() == "Ano?"
        out, _ = tools.run("language", {"action": "set_language", "language": "Klingonisch"})
        assert "keine Sprache" in out
        assert len(persona.LANGS) == 32
    finally:
        persona.set_language("de"); persona.set_address("sir")
