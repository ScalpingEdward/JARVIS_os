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
