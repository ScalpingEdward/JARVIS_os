import pytest

from app.assistant.tools import _dashboard_cards, _notes
from app.dashboard_layout import service as lay


def setup_function() -> None:
    lay.reset()
    for n in lay.notes():
        lay.set_note(n["id"], delete=True)


def test_default_layout_and_a_card_moves_by_its_name() -> None:
    assert lay.get()["left"] == ["trading", "watch"]
    out = lay.place("Instagram", "left", 1)
    assert out["left"] == ["insta", "trading", "watch"] and "insta" not in out["right"]
    out = lay.place("smart money", "hidden")
    assert "smart" in out["hidden"]


def test_added_cards_and_removal() -> None:
    out = lay.add("price", "right", "Gold")
    cid = out["right"][0]
    assert out["labels"][cid] == "Kurs: Gold" and out["custom"][cid]["config"]["name"] == "Gold"
    out = lay.place("Gold", "left")                       # found by its watchlist name
    assert out["left"][-1] == cid
    out = lay.remove("Kurs: Gold")
    assert cid not in out["custom"] and cid not in out["left"]
    out = lay.remove("Post")                              # built-in: only hidden
    assert "mail" in out["hidden"]


def test_a_broken_layout_is_refused() -> None:
    with pytest.raises(lay.LayoutError):
        lay.save({"left": ["trading", "trading"], "right": [], "hidden": [], "custom": {}})
    with pytest.raises(lay.LayoutError):
        lay.save({"left": ["nope"], "right": [], "hidden": [], "custom": {}})
    with pytest.raises(lay.LayoutError):
        lay.add("price", "right", "")
    out = lay.save({"left": ["trading"], "right": [], "hidden": [], "custom": {}})
    assert set(out["hidden"]) == {"watch", "insta", "mail", "smart"}   # no built-in card is lost


def test_auron_tools() -> None:
    r = _dashboard_cards("add", card_type="notes", side="left")
    assert r["left"][0] == "Notizen"
    assert "error" in _dashboard_cards("place", card="Wetter", side="left")
    n = _notes("add", text="EA für ORB besprechen")["notes"][0]
    assert n["by"] == "auron" and not n["done"]
    assert _notes("done", note_id=n["id"])["notes"][0]["done"] is True
