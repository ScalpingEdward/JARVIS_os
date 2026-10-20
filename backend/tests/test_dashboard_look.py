import pytest

from app.dashboard_layout import look
from app.dashboard_layout.service import _write


@pytest.fixture(autouse=True)
def clean():
    _write(look.KEY, {"version": 0, "look": {}}); _write(look.HISTORY_KEY, [])
    yield
    _write(look.KEY, {"version": 0, "look": {}}); _write(look.HISTORY_KEY, [])


def test_auron_changes_part_of_the_look_and_undo_steps_back():
    look.save({"theme": {"accent": "#4fd8ff", "style": "frosted"}, "room": "lounge", "cards": {"tileTrading": {"size": 1.12}}})
    d = look.change(theme={"accent": "#f5b84a"}, card="trading", card_style={"num": 1.25})
    assert d["look"]["theme"] == {"accent": "#f5b84a", "style": "frosted"}
    assert d["look"]["cards"]["tileTrading"] == {"size": 1.12, "num": 1.25} and d["look"]["room"] == "lounge"
    d = look.change(room="earth", card="all", card_style={"font": "sora"})
    assert d["look"]["room"] == "earth" and all(v["font"] == "sora" for v in d["look"]["cards"].values())
    assert look.undo()["look"]["room"] == "lounge"
    assert look.undo()["look"]["theme"]["accent"] == "#4fd8ff"


def test_a_phone_without_cards_keeps_them_and_nonsense_is_refused():
    look.save({"theme": {"accent": "#4fd8ff"}, "room": "noir", "cards": {"tileWatch": {"size": 1.25}}})
    assert look.save({"theme": {"accent": "#3ddc97"}, "room": "noir"})["look"]["cards"] == {"tileWatch": {"size": 1.25}}
    for bad in ({"theme": {"style": "glitter"}}, {"room": "mars"}, {"card_style": {"size": 3}}):
        with pytest.raises(look.LayoutError):
            look.change(**bad)
    v = look.get()["version"]
    assert look.save(look.get()["look"])["version"] == v     # nothing new: no new version
