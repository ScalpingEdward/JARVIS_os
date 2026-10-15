import json

import pytest

from signal_copier import profiles
from signal_copier.profiles import ProfileError


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "PROFILES", tmp_path / "profiles")
    return tmp_path


def test_template_is_demo_only_and_has_no_account():
    t = json.loads(profiles.TEMPLATE.read_text(encoding="utf-8"))
    assert t["allow_live"] is False and t["login"] is None and t["initial_balance"] is None


def test_create_copies_the_template_and_refuses_twice(home):
    config = profiles.create("roboforex_cent")
    assert json.loads(config.read_text(encoding="utf-8"))["allow_live"] is False
    assert profiles.names() == ["roboforex_cent"]
    with pytest.raises(ProfileError, match="exists"):
        profiles.create("roboforex_cent")


def test_names_are_plain_so_they_work_as_folder_and_shortcut():
    for bad in ["", "Robo Forex", "../x", "a/b", "ÄÖ"]:
        with pytest.raises(ProfileError):
            profiles.folder(bad)


def test_pick_runs_the_only_profile_and_asks_when_there_are_more(home):
    with pytest.raises(ProfileError, match="no profile yet"):
        profiles.pick(None)
    profiles.create("puprime_demo")
    assert profiles.pick(None) == "puprime_demo"
    profiles.create("roboforex_live")
    with pytest.raises(ProfileError, match="several"):
        profiles.pick(None)
    assert profiles.pick("roboforex_live") == "roboforex_live"
    with pytest.raises(ProfileError, match="no profile 'x'"):
        profiles.pick("x")
